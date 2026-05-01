from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Iterable

from openai import OpenAI
from pydantic import ValidationError

from .models import ClaimFields, ClaimSessionState, LLMExtraction
from .prompts import EXTRACTION_USER_TEMPLATE, SYSTEM_PROMPT


REQUIRED_FIELDS = [
    "date_of_incident",
    "zip_code",
    "disaster_type",
    "damage_type",
    "damage_description",
    "receipts_or_estimates",
    "requested_relief",
]

FIELD_LABELS = {
    "date_of_incident": "incident date",
    "zip_code": "damaged property ZIP code",
    "disaster_type": "type of disaster",
    "damage_type": "primary damage type",
    "damage_description": "damage description",
    "receipts_or_estimates": "receipts, estimates, photos, or document status",
    "requested_relief": "requested FEMA assistance",
}

QUESTION_BANK = {
    "date_of_incident": "I can help format this, but I need the incident date. What exact date did the disaster damage happen?",
    "zip_code": "What is the ZIP code for the damaged property?",
    "disaster_type": "What kind of disaster caused the damage, such as flood, wildfire, hurricane, tornado, or severe storm?",
    "damage_type": "What was the main type of damage: roof, structure, personal property, utilities, vehicle, or temporary housing?",
    "damage_description": "In one or two sentences, what was damaged and how did it affect your ability to safely live there?",
    "receipts_or_estimates": "Do you have receipts, contractor estimates, invoices, photos, or insurance letters? It is okay to say none are available yet.",
    "requested_relief": "What help are you asking FEMA for, such as home repair, temporary lodging, personal property, or serious needs assistance?",
}

ILLEGAL_PATTERNS = [
    r"\blie\b",
    r"\bfake\b",
    r"\bforge\b",
    r"\binflat(e|ed|ing)\b",
    r"\bmake up\b",
    r"\bpretend\b",
]


def merge_claim(existing: ClaimFields, extracted: ClaimFields) -> ClaimFields:
    merged = existing.model_copy(deep=True)
    for field_name, value in extracted.model_dump().items():
        if field_name == "stafford_act_terms":
            if value:
                merged.stafford_act_terms = list(dict.fromkeys(value))
            continue
        if value not in (None, "", []):
            setattr(merged, field_name, value)
    return merged


def missing_fields(claim: ClaimFields) -> list[str]:
    data = claim.model_dump()
    return [field for field in REQUIRED_FIELDS if not data.get(field)]


def next_question(missing: Iterable[str]) -> str | None:
    for field_name in missing:
        return QUESTION_BANK[field_name]
    return None


def analyze_with_agent(user_text: str, state: ClaimSessionState | None) -> tuple[ClaimSessionState, str | None]:
    current = state or ClaimSessionState()
    if _is_illegal_request(user_text):
        return current, (
            "I cannot help create or inflate a FEMA claim with false information. "
            "I can help prepare a truthful, fact-based claim using only what happened and what documents are available."
        )

    extraction = _extract_with_openai(user_text, current) or _extract_locally(user_text, current)
    if extraction.refusal:
        return current, extraction.refusal

    updated_claim = merge_claim(current.claim, extraction.claim)
    updated_claim = _complete_formal_language(updated_claim)
    updated_state = ClaimSessionState(
        claim=updated_claim,
        asked_fields=list(dict.fromkeys([*current.asked_fields, *missing_fields(updated_claim)])),
    )
    return updated_state, None


def _is_illegal_request(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered) for pattern in ILLEGAL_PATTERNS)


def _extract_with_openai(user_text: str, state: ClaimSessionState) -> LLMExtraction | None:
    if os.getenv("ENABLE_OPENAI", "").lower() not in {"1", "true", "yes"}:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None

    client = OpenAI()
    state_json = state.claim.model_dump_json(indent=2)
    prompt = EXTRACTION_USER_TEMPLATE.format(state_json=state_json, user_text=user_text)
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return LLMExtraction.model_validate_json(content)
    except (ValidationError, json.JSONDecodeError, Exception):
        return None


def _extract_locally(user_text: str, state: ClaimSessionState) -> LLMExtraction:
    text = user_text.strip()
    lowered = text.lower()
    claim = ClaimFields()

    claim.zip_code = _extract_zip(text)
    claim.date_of_incident = _extract_date(text)
    claim.disaster_type = _detect_disaster_type(lowered)
    claim.damage_type = _detect_damage_type(lowered)
    if len(text) > 20 and (not state.claim.damage_description or _looks_like_damage_story(lowered)):
        claim.damage_description = text
    claim.receipts_or_estimates = _detect_documents(text, lowered)
    claim.requested_relief = _detect_requested_relief(text, lowered)
    claim.stafford_act_terms = _terms_for(claim)
    return LLMExtraction(claim=claim)


def _extract_zip(text: str) -> str | None:
    match = re.search(r"\b(\d{5})(?:-\d{4})?\b", text)
    return match.group(1) if match else None


def _extract_date(text: str) -> str | None:
    # 1. Numeric check (e.g., 04/27/2026)
    numeric = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b", text)
    if numeric:
        month, day, year = numeric.groups()
        year = f"20{year}" if len(year) == 2 else year
        try:
            return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            return None

    # 2. Textual check (e.g., April 27th)
    month_names = (
        "january|february|march|april|may|june|july|august|september|october|november|december|"
        "jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec"
    )
    written = re.search(rf"\b({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:\s*,?\s*)?(\d{{4}})?\b", text, re.IGNORECASE)
    
    if not written:
        return None
        
    month_text, day, year = written.groups()
    
    # Failsafe: Default to 2026 if year is omitted
    if not year:
        year = "2026"
        
    try:
        m_short = month_text[:3].title()
        return datetime.strptime(f"{m_short} {day} {year}", "%b %d %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _detect_disaster_type(lowered: str) -> str | None:
    candidates = {
        "hurricane": ["hurricane", "storm surge"],
        "flood": ["flood", "flooded", "inundation", "water rose"],
        "wildfire": ["wildfire", "fire", "smoke"],
        "tornado": ["tornado", "twister"],
        "severe storm": ["storm", "wind", "hail", "rain"],
        "earthquake": ["earthquake", "quake"],
    }
    for label, needles in candidates.items():
        if any(needle in lowered for needle in needles):
            return label
    return None


def _detect_damage_type(lowered: str) -> str | None:
    candidates = {
        "roof": ["roof", "shingle", "ceiling leak"],
        "structure": ["wall", "foundation", "structure", "window", "door", "tree"],
        "personal property": ["furniture", "clothes", "appliance", "belongings", "personal property"],
        "utilities": ["power", "electric", "water heater", "plumbing", "utilities"],
        "vehicle": ["car", "truck", "vehicle"],
        "temporary housing": ["hotel", "motel", "cannot stay", "unlivable", "unsafe to live"],
    }
    for label, needles in candidates.items():
        if any(needle in lowered for needle in needles):
            return label
    return None


def _looks_like_damage_story(lowered: str) -> bool:
    damage_words = [
        "damage", "damaged", "destroyed", "ruined", "hit", "leak", "flood", 
        "burn", "smoke", "roof", "wall", "tree", "unsafe", "unlivable"
    ]
    return any(word in lowered for word in damage_words)


def _detect_documents(text: str, lowered: str) -> str | None:
    # Match actual docs
    if any(word in lowered for word in ["receipt", "estimate", "invoice", "photo", "insurance", "contractor"]):
        return text
    
    # Match negative responses (including strict "no")
    negatives = ["none", "dont have", "don't have", "no receipts", "no estimate", "nothing", "n/a", "i dont"]
    if any(neg in lowered for neg in negatives) or lowered.strip() == "no":
        return "None available at the time of claim preparation."
    return None


def _detect_requested_relief(text: str, lowered: str) -> str | None:
    relief_terms = ["repair", "lodging", "hotel", "rental", "personal property", "replace", "assistance", "help", "money"]
    if any(term in lowered for term in relief_terms):
        return text
    
    # Catch-all for vague demo responses
    if any(phrase in lowered for phrase in ["idk", "not sure", "everything", "any", "standard"]):
        return "Standard FEMA housing and individual assistance."
        
    # Ultimate Hackathon Failsafe: If they typed a decent length answer, just accept it
    if len(text.strip()) > 4:
        return text
        
    return None


def _terms_for(claim: ClaimFields) -> list[str]:
    terms = ["disaster-caused damage"]
    joined = " ".join(filter(None, [claim.disaster_type, claim.damage_type, claim.damage_description])).lower()
    if any(x in joined for x in ["roof", "tree", "wind"]):
        terms.extend(["essential home repair", "structural envelope breached by wind-driven debris"])
    if any(x in joined for x in ["flood", "water"]):
        terms.extend(["flood inundation", "habitability"])
    if any(x in joined for x in ["hotel", "lodging", "unlivable"]):
        terms.append("temporary housing assistance")
    if any(x in joined for x in ["furniture", "belongings", "appliance"]):
        terms.append("personal property assistance")
    return list(dict.fromkeys(terms))


def _complete_formal_language(claim: ClaimFields) -> ClaimFields:
    updated = claim.model_copy(deep=True)
    updated.stafford_act_terms = _terms_for(updated)

    if updated.damage_description:
        terms = ", ".join(updated.stafford_act_terms)
        description = updated.damage_description.strip().rstrip(".")
        updated.statement_of_loss = (
            f"On or about {updated.date_of_incident or 'the reported incident date'}, "
            f"the applicant reports {updated.disaster_type or 'a disaster event'} causing "
            f"{updated.damage_type or 'property'} damage at the damaged property in ZIP code "
            f"{updated.zip_code or 'not yet provided'}. The reported loss is described as: "
            f"{description}. This is characterized for claim preparation as {terms}."
        )
    return updated