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
    # Clean up characters that break Latin-1 (FPDF default encoding)
    replacements = {
        "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'",
        "\u201c": '"', "\u201d": '"', "\u2022": "-", "\u00a0": " ",
    }
    for original, replacement in replacements.items():
        value = value.replace(original, replacement)
    # Encode/Decode to force compatibility with Latin-1
    return value.encode("latin-1", "replace").decode("latin-1")

def _multi_cell_section(pdf: FPDF, label: str, value: str) -> None:
    """Renders a full-width section with a bold label and wrapped text."""
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(190, 6, _pdf_text(label), ln=True)
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

    # --- SECTION 1: CLAIM SUMMARY ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Claim Summary", ln=True)
    pdf.set_draw_color(28, 64, 84)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Use a 50mm label width and 140mm value width to keep text on screen
    summary_rows = [
        ("Date of Incident", getattr(claim, 'date_of_incident', 'Not provided')),
        ("ZIP Code", getattr(claim, 'zip_code', 'Not provided')),
        ("Disaster Type", getattr(claim, 'disaster_type', 'Not provided')),
        ("Damage Type", getattr(claim, 'damage_type', 'Not provided')),
        ("Evidence Total", f"${claim.evidence_total:,.2f}" if getattr(claim, 'evidence_total', None) else "Not provided"),
    ]

    for label, value in summary_rows:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(50, 7, _pdf_text(f"{label}:"), border=0)
        pdf.set_font("Helvetica", "", 10)
        # Using 140 width and ln=True ensures the next row starts below
        pdf.multi_cell(140, 7, _pdf_text(str(value)), ln=True)

    pdf.ln(3)
    
    # Statement of Loss (Large text block)
    statement = getattr(claim, 'statement_of_loss', getattr(claim, 'damage_description', 'Not provided'))
    _multi_cell_section(pdf, "Statement of Loss", statement)

    # Evidence Uploads
    if evidence_items:
        evidence_summary = ""
        for item in evidence_items:
            evidence_summary += f"- {item.filename}: {len(item.extracted_text)} characters extracted\n"
        _multi_cell_section(pdf, "Supporting Evidence Documents", evidence_summary)

    # --- SECTION 2: LEGAL CONTEXT ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, "Legal Context & Regulatory Alignment", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    if citations:
        for i, cit in enumerate(citations):
            title = getattr(cit, 'title', getattr(cit, 'source', f"Citation {i+1}"))
            excerpt = getattr(cit, 'excerpt', getattr(cit, 'text', 'No text excerpt provided.'))
            _multi_cell_section(pdf, f"Reference: {title}", excerpt)
    else:
        pdf.set_font("Helvetica", "I", 10)
        pdf.multi_cell(190, 6, "No specific Stafford Act citations were retrieved for this claim description.")

    # Red Team Review Notes
    if red_team_notes:
        pdf.ln(4)
        _multi_cell_section(pdf, "Adjuster Skepticism Notes (Self-Review)", "\n".join(f"- {note}" for note in red_team_notes))

    # Footer Metadata
    pdf.set_y(-25)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(0, 5, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ln=True, align="R")

    # Output to base64
    # Handling potential type differences in FPDF output across versions
    pdf_output = pdf.output(dest="S")
    if isinstance(pdf_output, str):
        pdf_output = pdf_output.encode("latin-1")
    
    return base64.b64encode(pdf_output).decode("ascii")

def pdf_data_url(pdf_base64: str) -> str:
    return f"data:application/pdf;base64,{pdf_base64}"