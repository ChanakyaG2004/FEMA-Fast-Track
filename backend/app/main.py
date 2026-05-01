from __future__ import annotations

import json
import re
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

# --- CORS CONFIGURATION ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "fema-fast-track.vercel.app",  # 👈 IMPORTANT
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

# HELPER: Fixes the 500 ValidationError by converting objects to dicts
def serialize_citations(cits):
    if not cits: return []
    
    clean_citations = []
    for c in cits:
        # Try every possible way to turn this object into a dictionary
        if hasattr(c, 'model_dump'):
            clean_citations.append(c.model_dump())
        elif hasattr(c, 'dict'):
            clean_citations.append(c.dict())
        elif hasattr(c, '__dict__'):
            clean_citations.append(vars(c))
        else:
            clean_citations.append(c) # Last resort
            
    return clean_citations

@app.post("/api/analyze-claim", response_model=AnalyzeClaimResponse)
async def analyze_claim(request: Request) -> AnalyzeClaimResponse:
    payload, uploads = await _parse_payload(request)
    
    state, refusal = analyze_with_agent(payload.text, payload.session_state)
    
    # Manual Intercept for Date
    date_pattern = r"(January|February|March|April|May|June|July|August|September|October|November|December|\d{1,2}[/-]\d{1,2}[/-])\s*\d{1,2}?(st|nd|rd|th)?\s*,?\s*202\d"
    if re.search(date_pattern, payload.text, re.IGNORECASE):
        state.claim.incident_date = payload.text

    evidence_items = await extract_evidence(uploads)
    evidence_warnings: list[str] = []
    
    if evidence_items:
        state.claim, evidence_warnings = apply_evidence_to_claim(state.claim, evidence_items)
        state.evidence_items.extend(evidence_items)

    raw_citations = retrieve_relevant_clauses(_rag_query(payload.text, state.claim))
    
    # BRUTE FORCE: Convert whatever object RAG returns into a raw dictionary
    citations = []
    for c in raw_citations:
        citations.append({
            "title": getattr(c, "title", "Legal Reference"),
            "text": getattr(c, "text", str(c))
        })
        
    state.legal_citations = citations
    
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

    state.claim, red_team_notes = red_team_review(state.claim, citations, evidence_warnings)
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
        uploads = [value for _, value in form.multi_items() if hasattr(value, "filename")]
        payload = AnalyzeClaimRequest.model_validate({"text": text, "session_state": state})
        return payload, uploads
    body = await request.json()
    return AnalyzeClaimRequest.model_validate(body), []

def _rag_query(text: str, claim) -> str:
    return " ".join(filter(None, [text, claim.disaster_type, claim.damage_type]))