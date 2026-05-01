from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator


class ClaimStatus(str, Enum):
    NEEDS_INFO = "needs_info"
    COMPLETE = "complete"


class ClaimFields(BaseModel):
    date_of_incident: str | None = Field(
        default=None,
        description="Exact or best-known incident date in YYYY-MM-DD format.",
    )
    zip_code: str | None = Field(
        default=None,
        description="Five digit ZIP code where the damaged property is located.",
    )
    disaster_type: str | None = Field(
        default=None,
        description="Disaster event such as hurricane, flood, wildfire, severe storm, tornado, or earthquake.",
    )
    damage_type: str | None = Field(
        default=None,
        description="Primary category of damage, such as roof, structure, personal property, utilities, vehicle, or temporary housing.",
    )
    damage_description: str | None = Field(
        default=None,
        description="Plain-language summary of what happened and what was damaged.",
    )
    receipts_or_estimates: str | None = Field(
        default=None,
        description="Known receipts, contractor estimates, invoices, photos, insurance documents, or an explicit statement that none are available yet.",
    )
    requested_relief: str | None = Field(
        default=None,
        description="What FEMA assistance is being requested, such as home repair, personal property, temporary lodging, or other needs assistance.",
    )
    stafford_act_terms: list[str] = Field(
        default_factory=list,
        description="Standard Stafford Act-aligned terms that fit the completed facts. Do not include legal citations.",
    )
    statement_of_loss: str | None = Field(
        default=None,
        description="Formal FEMA-ready statement of loss using completed facts only.",
    )
    evidence_total: float | None = Field(
        default=None,
        description="Total dollar amount extracted from uploaded receipts or estimates.",
    )
    evidence_summary: str | None = Field(
        default=None,
        description="Short summary of uploaded evidence text, dates, and totals.",
    )

    @field_validator("zip_code")
    @classmethod
    def validate_zip(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if len(cleaned) == 5 and cleaned.isdigit():
            return cleaned
        return None


class ClaimSessionState(BaseModel):
    claim: ClaimFields = Field(default_factory=ClaimFields)
    asked_fields: list[str] = Field(default_factory=list)
    legal_citations: list["LegalCitation"] = Field(default_factory=list)
    evidence_items: list["EvidenceItem"] = Field(default_factory=list)
    red_team_notes: list[str] = Field(default_factory=list)


class AnalyzeClaimRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=8000)
    session_state: ClaimSessionState | None = Field(
        default=None,
        validation_alias=AliasChoices("session_state", "state"),
    )


class AnalyzeClaimResponse(BaseModel):
    status: ClaimStatus
    missing_fields: list[str]
    question: str | None = None
    claim: ClaimFields
    session_state: ClaimSessionState
    pdf_base64: str | None = None
    pdf_url: str | None = None
    filename: str | None = None
    refusal: str | None = None
    legal_citations: list["LegalCitation"] = Field(default_factory=list)
    evidence_items: list["EvidenceItem"] = Field(default_factory=list)
    evidence_warnings: list[str] = Field(default_factory=list)
    red_team_notes: list[str] = Field(default_factory=list)


class LLMExtraction(BaseModel):
    refusal: str | None = None
    claim: ClaimFields = Field(default_factory=ClaimFields)


class LLMMessage(BaseModel):
    role: Literal["system", "user"]
    content: str


JsonDict = dict[str, Any]


class LegalCitation(BaseModel):
    title: str
    source: str
    page: int | None = None
    excerpt: str


class EvidenceItem(BaseModel):
    filename: str
    content_type: str | None = None
    extracted_text: str = ""
    dates: list[str] = Field(default_factory=list)
    dollar_amounts: list[float] = Field(default_factory=list)
    total: float | None = None
    warning: str | None = None
