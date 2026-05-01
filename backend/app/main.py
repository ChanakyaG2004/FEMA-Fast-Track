from __future__ import annotations

import json
import re
import traceback
from typing import Optional, List

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
    description="Local, privacy-first FEMA claim preparation API.",
    version="0.1.0",
)

# ---------------- CORS ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://fema-fast-track.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------- MAIN ENDPOINT ----------------
@app.post("/api/analyze-claim", response_model=AnalyzeClaimResponse)
async def analyze_claim(request: Request) -> AnalyzeClaimResponse:
    try:
        payload, uploads = await _parse_payload(request)

        state, refusal = analyze_with_agent(payload.text, payload.session_state)

        # --- Date intercept ---
        date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}[/-]\d{1,2}[/-])\s*\d{1,2}?(st|nd|rd|th)?\s*,?\s*202\d"
        if re.search(date_pattern, payload.text, re.IGNORECASE):
            state.claim.incident_date = payload.text

        # --- Evidence ---
        evidence_items = await extract_evidence(uploads)
        evidence_warnings: list[str] = []

        if evidence_items:
            state.claim, evidence_warnings = apply_evidence_to_claim(
                state.claim,
                evidence_items
            )
            state.evidence_items.extend(evidence_items)

        # --- RAG citations ---
        raw_citations = retrieve_relevant_clauses(
            _rag_query(payload.text, state.claim)
        )

        citations = []
        for c in raw_citations or []:
            citations.append({
                "title": getattr(c, "title", "Legal Reference"),
                "text": getattr(c, "text", str(c))
            })

        state.legal_citations = citations

        missing = missing_fields(state.claim)

        # --- Early return: refusal ---
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

        # --- Early return: missing fields ---
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

        # ---------------- SAFE RED TEAM ----------------
        try:
            red_team_notes = red_team_review(
                state.claim,
                citations,
                evidence_warnings
            )
        except Exception as e:
            print("⚠️ red_team_review failed:", e)
            red_team_notes = []

        # ---------------- SAFE PDF ----------------
        try:
            pdf_base64 = generate_claim_pdf_base64(
                state.claim,
                citations,
                state.evidence_items,
                red_team_notes
            )
        except Exception as e:
            print("⚠️ PDF generation failed:", e)
            pdf_base64 = None

        # ---------------- FINAL RESPONSE ----------------
        return AnalyzeClaimResponse(
            status=ClaimStatus.COMPLETE,
            missing_fields=[],
            question=None,
            claim=state.claim,
            session_state=state,
            pdf_base64=pdf_base64,
            pdf_url=pdf_data_url(pdf_base64) if pdf_base64 else None,
            filename="fema-fast-track-claim.pdf",
            legal_citations=citations,
            evidence_items=state.evidence_items,
            evidence_warnings=evidence_warnings,
            red_team_notes=red_team_notes,
        )

    except Exception as e:
        # 🔥 THIS WILL SHOW REAL ERROR IN RENDER LOGS
        print("🔥 UNHANDLED ERROR:", e)
        print(traceback.format_exc())
        raise


# ---------------- HELPERS ----------------
async def _parse_payload(request: Request) -> tuple[AnalyzeClaimRequest, list[UploadFile]]:
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        text = str(form.get("text") or "")
        state_raw = form.get("session_state") or form.get("state")
        state = json.loads(str(state_raw)) if state_raw else None

        uploads = [
            value for _, value in form.multi_items()
            if hasattr(value, "filename")
        ]

        payload = AnalyzeClaimRequest.model_validate({
            "text": text,
            "session_state": state
        })
        return payload, uploads

    body = await request.json()
    return AnalyzeClaimRequest.model_validate(body), []


def _rag_query(text: str, claim) -> str:
    return " ".join(filter(None, [
        text,
        getattr(claim, "disaster_type", None),
        getattr(claim, "damage_type", None),
    ]))