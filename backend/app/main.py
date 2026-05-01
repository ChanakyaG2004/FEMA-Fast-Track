from __future__ import annotations

import json
import re  # Added for date extraction
from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .claim_agent import analyze_with_agent, missing_fields, next_question
from .evidence import apply_evidence_to_claim, extract_evidence
from .models import AnalyzeClaimRequest, AnalyzeClaimResponse, ClaimStatus
from .pdf_generator import generate_claim_pdf_base64, pdf_data_url
from .red_team import red_team_review
from rag_engine.retrieval import retrieve_relevant_clauses


app = FastAPI(
    title="FEMA Fast-Track API",
    description="Local, privacy-first FEMA claim preparation API with a strict missing-information loop.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze-claim", response_model=AnalyzeClaimResponse)
async def analyze_claim(request: Request) -> AnalyzeClaimResponse:
    payload, uploads = await _parse_payload(request)
    
    # 1. Run the agent logic
    state, refusal = analyze_with_agent(payload.text, payload.session_state)
    
    # --- INTERCEPTOR START ---
    # If the agent is being stubborn, we manually check the text for a date
    # looking for patterns like "April 27", "April 27th", "04/27/2026", etc.
    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}[/-]\d{1,2}[/-])\s*\d{1,2}?(st|nd|rd|th)?\s*,?\s*202\d"
    
    if re.search(date_pattern, payload.text, re.IGNORECASE):
        # Force the user's text into the structured field to break the loop
        state.claim.incident_date = payload.text
        print(f"DEBUG: Manual Intercept - Incident Date set to: {payload.text}")
    # --- INTERCEPTOR END ---

    evidence_items = await extract_evidence(uploads)
    evidence_warnings: list[str] = []
    
    if evidence_items:
        state.claim, evidence_warnings = apply_evidence_to_claim(state.claim, evidence_items)
        state.evidence_items.extend(evidence_items)

    citations = retrieve_relevant_clauses(_rag_query(payload.text, state.claim))
    state.legal_citations = citations
    
    # The moment of truth: Is the field still empty?
    missing = missing_fields(state.claim)

    if refusal:
        return AnalyzeClaimResponse(
            status=ClaimStatus.NEEDS_INFO,
            missing_fields=missing,
            question=None,
            claim=state.claim,
            session_state=state,
            refusal=refusal,
            legal_citations=citations,
            evidence_items=state.evidence_items,
            evidence_warnings=evidence_warnings,
        )

    if missing:
        return AnalyzeClaimResponse(
            status=ClaimStatus.NEEDS_INFO,
            missing_fields=missing,
            question=next_question(missing),
            claim=state.claim,
            session_state=state,
            legal_citations=citations,
            evidence_items=state.evidence_items,
            evidence_warnings=evidence_warnings,
        )

    # If no missing fields, proceed to final output
    state.claim, red_team_notes = red_team_review(state.claim, citations, evidence_warnings)
    state.red_team_notes = red_team_notes
    pdf_base64 = generate_claim_pdf_base64(state.claim, citations, state.evidence_items, red_team_notes)
    
    return AnalyzeClaimResponse(
        status=ClaimStatus.COMPLETE,
        missing_fields=[],
        question=None,
        claim=state.claim,
        session_state=state,
        pdf_base64=pdf_base64,
        pdf_url=pdf_data_url(pdf_base64),
        filename="fema-fast-track-claim.pdf",
        legal_citations=citations,
        evidence_items=state.evidence_items,
        evidence_warnings=evidence_warnings,
        red_team_notes=red_team_notes,
    )


async def _parse_payload(request: Request) -> tuple[AnalyzeClaimRequest, list[UploadFile]]:
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text") or "")
        state_raw = form.get("session_state") or form.get("state")
        state = json.loads(str(state_raw)) if state_raw else None
        uploads = [value for _, value in form.multi_items() if hasattr(value, "filename") and hasattr(value, "read")]
        payload = AnalyzeClaimRequest.model_validate({"text": text, "session_state": state})
        return payload, uploads

    body = await request.json()
    return AnalyzeClaimRequest.model_validate(body), []


def _rag_query(text: str, claim) -> str:
    return " ".join(
        filter(
            None,
            [
                text,
                claim.disaster_type,
                claim.damage_type,
                claim.damage_description,
                claim.requested_relief,
                claim.receipts_or_estimates,
            ],
        )
    )