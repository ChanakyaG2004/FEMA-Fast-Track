from __future__ import annotations
import base64
from datetime import datetime
from fpdf import FPDF
from .models import ClaimFields, EvidenceItem, LegalCitation

class ClaimPDF(FPDF):
    def header(self) -> None:
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 8, "FEMA Fast-Track Claim Preparation Packet", ln=True, align="C")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 5, "Prepared locally for survivor review before FEMA submission", ln=True, align="C")
        self.ln(6)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} of {{nb}}", align="C")

def _pdf_text(value: str) -> str:
    if not value:
        return "Not provided"
    # Clean up special characters that break Latin-1 encoding
    replacements = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u00a0": " ",
    }
    for original, replacement in replacements.items():
        value = value.replace(original, replacement)
    return value.encode("latin-1", "replace").decode("latin-1")

def _multi_cell(pdf: FPDF, label: str, value: str) -> None:
    pdf.set_font("Helvetica", "B", 10)
    # Using 190 instead of 0 to prevent "Not enough horizontal space" errors
    pdf.cell(190, 6, _pdf_text(label), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(190, 5, _pdf_text(value))
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
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Claim Summary", ln=True)
    pdf.set_draw_color(28, 64, 84)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Use getattr to safely handle potentially missing fields
    summary_rows = [
        ("Date of Incident", getattr(claim, 'date_of_incident', 'Not provided')),
        ("ZIP Code", getattr(claim, 'zip_code', 'Not provided')),
        ("Disaster Type", getattr(claim, 'disaster_type', 'Not provided')),
        ("Damage Type", getattr(claim, 'damage_type', 'Not provided')),
    ]

    for label, value in summary_rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(58, 7, _pdf_text(f"{label}:"), border=0)
        pdf.set_font("Helvetica", "", 10)
        # Using fixed width 132 (190 total - 58 label)
        pdf.multi_cell(132, 7, _pdf_text(str(value)))

    pdf.ln(3)
    statement = getattr(claim, 'statement_of_loss', getattr(claim, 'damage_description', 'Not provided'))
    _multi_cell(pdf, "Statement of Loss", statement)

    if evidence_items:
        evidence_summary = ""
        for item in evidence_items:
            evidence_summary += f"- {item.filename}: {len(item.extracted_text)} chars extracted\n"
        _multi_cell(pdf, "Evidence Extracted", evidence_summary)

    # New Page for Legal Context
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Legal Context & Review", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    if citations:
        for i, cit in enumerate(citations):
            # Try to find whatever field name is coming through
            title = getattr(cit, 'title', getattr(cit, 'source', f"Citation {i+1}"))
            text = getattr(cit, 'excerpt', getattr(cit, 'text', 'No text provided'))
            _multi_cell(pdf, str(title), str(text))
    
    if red_team_notes:
        _multi_cell(pdf, "Review Notes", "\n".join(f"- {n}" for n in red_team_notes))

    # Output to base64
    # Note: pdf.output(dest='S') returns bytes in newer fpdf2, 
    # but let's ensure compatibility
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode("latin-1")
    
    return base64.b64encode(pdf_bytes).decode("ascii")

def pdf_data_url(pdf_base64: str) -> str:
    return f"data:application/pdf;base64,{pdf_base64}"