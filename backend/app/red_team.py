from __future__ import annotations

import os

from openai import OpenAI

from .claim_agent import missing_fields
from .models import ClaimFields, LegalCitation


RED_TEAM_PROMPT = """You are a skeptical FEMA claims adjuster. Review the draft for unsupported facts, missing elements, math inconsistencies, and terminology that goes beyond cited Stafford Act context. Return concise JSON only: {"approved": boolean, "notes": ["..."], "revision": "..."}. Do not add legal citations."""


def red_team_review(claim: ClaimFields, citations: list[LegalCitation], evidence_warnings: list[str]) -> tuple[ClaimFields, list[str]]:
    notes = _local_red_team(claim, citations, evidence_warnings)
    if os.getenv("ENABLE_OPENAI", "").lower() in {"1", "true", "yes"} and os.getenv("OPENAI_API_KEY"):
        notes.extend(_openai_red_team(claim, citations, evidence_warnings))
    revised = _revise_claim(claim, notes)
    return revised, list(dict.fromkeys(notes))


def _local_red_team(claim: ClaimFields, citations: list[LegalCitation], evidence_warnings: list[str]) -> list[str]:
    notes: list[str] = []
    missing = missing_fields(claim)
    if missing:
        notes.append(f"Cannot finalize while required fields are missing: {', '.join(missing)}.")
    if not citations:
        notes.append("No Stafford Act vector citations were retrieved; do not finalize without legal context.")
    if claim.damage_type == "roof":
        description = (claim.damage_description or "").lower()
        if "roof" not in description and "breach" not in description and "leak" not in description:
            notes.append("The claim is categorized as roof damage but does not explicitly describe roof impact, breach, or leakage.")
    notes.extend(evidence_warnings)
    return notes


def _revise_claim(claim: ClaimFields, notes: list[str]) -> ClaimFields:
    revised = claim.model_copy(deep=True)
    if notes and revised.statement_of_loss:
        revised.statement_of_loss = (
            f"{revised.statement_of_loss} Red-team review flags for applicant review: "
            f"{' '.join(notes)}"
        )
    return revised


def _openai_red_team(claim: ClaimFields, citations: list[LegalCitation], evidence_warnings: list[str]) -> list[str]:
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RED_TEAM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Claim JSON: {claim.model_dump_json()}\n"
                        f"Citations: {[citation.model_dump() for citation in citations]}\n"
                        f"Evidence warnings: {evidence_warnings}"
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        import json

        data = json.loads(content)
        return [str(note) for note in data.get("notes", [])]
    except Exception:
        return []
