from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO

from fpdf import FPDF

from .models import ClaimFields, EvidenceItem, LegalCitation


class ClaimPDF(FPDF):
    def header(self) -> None:
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, "FEMA Fast-Track Claim Preparation Packet", ln=True, align="C")
        self.set_font("Arial", "", 9)
        self.cell(0, 5, "Prepared locally for survivor review before FEMA submission", ln=True, align="C")
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align="C")


def _safe(value: str | None) -> str:
    return _pdf_text(value.strip()) if value and value.strip() else "Not provided"


def _pdf_text(value: str) -> str:
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
    }
    for original, replacement in replacements.items():
        value = value.replace(original, replacement)
    return value.encode("latin-1", "replace").decode("latin-1")


def _multi_cell(pdf: FPDF, label: str, value: str) -> None:
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, _pdf_text(label), ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 5, _pdf_text(value))
    pdf.ln(2)


def generate_claim_pdf_base64(
    claim: ClaimFields,
    citations: list[LegalCitation] | None = None,
    evidence_items: list[EvidenceItem] | None = None,
    red_team_notes: list[str] | None = None,
) -> str:
    citations = citations or []
    evidence_items = evidence_items or []
    red_team_notes = red_team_notes or []

    pdf = ClaimPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)

    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Claim Summary", ln=True)
    pdf.set_draw_color(28, 64, 84)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    summary_rows = [
        ("Date of Incident", _safe(claim.date_of_incident)),
        ("Damaged Property ZIP Code", _safe(claim.zip_code)),
        ("Disaster Type", _safe(claim.disaster_type)),
        ("Primary Damage Type", _safe(claim.damage_type)),
        ("Supporting Documents", _safe(claim.receipts_or_estimates)),
        ("Extracted Evidence Total", f"${claim.evidence_total:,.2f}" if claim.evidence_total is not None else "Not provided"),
    ]
    pdf.set_font("Arial", "", 10)
    for label, value in summary_rows:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(58, 7, _pdf_text(f"{label}:"), border=0)
        pdf.set_font("Arial", "", 10)
        pdf.multi_cell(0, 7, _pdf_text(value))

    pdf.ln(3)
    _multi_cell(pdf, "Statement of Loss", _safe(claim.statement_of_loss or claim.damage_description))

    terms = ", ".join(claim.stafford_act_terms) if claim.stafford_act_terms else "disaster-caused damage; essential home repair; habitability"
    _multi_cell(pdf, "Stafford Act-Aligned Terminology", terms)

    if evidence_items:
        evidence_summary = "\n".join(
            f"- {item.filename}: {len(item.extracted_text)} text characters extracted; "
            f"dates: {', '.join(item.dates) or 'none found'}; "
            f"amounts: {', '.join(f'${amount:,.2f}' for amount in item.dollar_amounts) or 'none found'}"
            for item in evidence_items
        )
        _multi_cell(pdf, "Evidence Extracted From Uploads", evidence_summary)

    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Requested Relief", ln=True)
    pdf.set_draw_color(28, 64, 84)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    _multi_cell(pdf, "Assistance Requested", _safe(claim.requested_relief))
    _multi_cell(
        pdf,
        "Basis for Request",
        (
            "The applicant reports disaster-caused damage affecting the safety, sanitation, "
            "or habitability of the property. The requested assistance is limited to documented "
            "or truthfully reported losses and should be reviewed against FEMA eligibility "
            "requirements before submission."
        ),
    )
    _multi_cell(
        pdf,
        "Document Checklist",
        (
            "- Government-issued identification\n"
            "- Proof of occupancy or ownership, if available\n"
            "- Insurance correspondence, if applicable\n"
            "- Contractor estimates, receipts, invoices, photos, or a written note that records are not yet available\n"
            "- Disaster photos and temporary lodging receipts, if applicable"
        ),
    )
    _multi_cell(
        pdf,
        "Truthfulness Notice",
        (
            "This packet is a preparation aid, not a FEMA determination. The survivor should "
            "review every statement for accuracy before submission. No legal citations or facts "
            "have been added beyond the provided claim information."
        ),
    )

    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "Retrieved Stafford Act Context", ln=True)
    pdf.set_draw_color(28, 64, 84)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    if citations:
        for index, citation in enumerate(citations, start=1):
            location = f"{citation.source}"
            if citation.page:
                location = f"{location}, p. {citation.page}"
            _multi_cell(pdf, f"Citation {index}: {citation.title}", f"{location}\n{citation.excerpt}")
    else:
        _multi_cell(pdf, "Citation Status", "No Stafford Act vector citations were retrieved.")

    if red_team_notes:
        _multi_cell(pdf, "Skeptical Adjuster Review", "\n".join(f"- {note}" for note in red_team_notes))

    pdf.set_font("Arial", "", 9)
    pdf.ln(3)
    pdf.cell(0, 5, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True)

    raw = pdf.output(dest="S").encode("latin-1")
    return base64.b64encode(raw).decode("ascii")


def pdf_data_url(pdf_base64: str) -> str:
    return f"data:application/pdf;base64,{pdf_base64}"
