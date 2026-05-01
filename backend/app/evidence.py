from __future__ import annotations

import re
from io import BytesIO

from PIL import Image
from pypdf import PdfReader
from pytesseract import pytesseract

from .models import ClaimFields, EvidenceItem


DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(r"(?<!\w)\$?\s?([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})|[0-9]+\.[0-9]{2})(?!\w)")


async def extract_evidence(files) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    for upload in files or []:
        raw = await upload.read()
        text = ""
        warning = None
        try:
            if upload.content_type == "application/pdf" or upload.filename.lower().endswith(".pdf"):
                text = _extract_pdf_text(raw)
            elif (upload.content_type or "").startswith("text/"):
                text = raw.decode("utf-8", "ignore")
            else:
                text = _extract_image_text(raw)
        except Exception as exc:
            warning = (
                "Could not read this file. Install the Tesseract system binary for image OCR "
                "or upload a clearer PDF/image."
            )
            text = ""

        amounts = _extract_amounts(text)
        evidence.append(
            EvidenceItem(
                filename=upload.filename,
                content_type=upload.content_type,
                extracted_text=text[:3000],
                dates=DATE_RE.findall(text),
                dollar_amounts=amounts,
                total=max(amounts) if amounts else None,
                warning=warning,
            )
        )
    return evidence


def apply_evidence_to_claim(claim: ClaimFields, evidence_items: list[EvidenceItem]) -> tuple[ClaimFields, list[str]]:
    updated = claim.model_copy(deep=True)
    warnings: list[str] = []
    totals = [item.total for item in evidence_items if item.total is not None]
    if totals:
        updated.evidence_total = round(sum(totals), 2)
        updated.evidence_summary = (
            f"{len(evidence_items)} uploaded evidence file(s) reviewed. "
            f"Extracted apparent total: ${updated.evidence_total:,.2f}."
        )
        if not updated.receipts_or_estimates:
            updated.receipts_or_estimates = updated.evidence_summary

    for item in evidence_items:
        if item.warning:
            warnings.append(f"{item.filename}: {item.warning}")

    text_amounts = _extract_amounts(" ".join(filter(None, [claim.damage_description, claim.requested_relief, claim.receipts_or_estimates])))
    if text_amounts and totals:
        claimed_total = max(text_amounts)
        evidence_total = sum(totals)
        if abs(claimed_total - evidence_total) > 1.0:
            warnings.append(
                f"Claim text mentions about ${claimed_total:,.2f}, but uploaded evidence totals about ${evidence_total:,.2f}. Please reconcile before submission."
            )
    return updated, warnings


def _extract_pdf_text(raw: bytes) -> str:
    reader = PdfReader(BytesIO(raw))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    if text.strip():
        return text
    return raw.decode("latin-1", "ignore")


def _extract_image_text(raw: bytes) -> str:
    image = Image.open(BytesIO(raw))
    return pytesseract.image_to_string(image)


def _extract_amounts(text: str) -> list[float]:
    amounts: list[float] = []
    for match in MONEY_RE.findall(text or ""):
        try:
            amounts.append(float(match.replace(",", "")))
        except ValueError:
            continue
    return amounts
