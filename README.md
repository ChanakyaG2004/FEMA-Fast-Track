# FEMA Fast-Track 🚀
**Accelerating Disaster Relief with AI-Powered Claim Preparation**

FEMA Fast-Track is a privacy-first, local-LLM-driven assistant that helps disaster victims prepare structured, legally-compliant claim documents in minutes instead of days.

## 🌟 The Problem
After a disaster, victims are often overwhelmed. Traditional FEMA applications are complex, leading to missing information, "red-flag" keywords, and months of delays.

## ✨ Our Solution
- **Strict Missing-Info Loop:** Our agent refuses to finalize a claim until every critical detail (date, ZIP, damage type) is captured.
- **Evidence Extraction:** Uses OCR to pull dates and costs directly from contractor estimates and receipts.
- **Red-Team Review:** An automated "Red-Team" agent checks for inconsistent data before submission.
- **Legal Alignment:** Maps casual descriptions to official Stafford Act terminology for higher approval rates.

## 🛠️ Tech Stack
- **Frontend:** React + Vite (Tailwind CSS)
- **Backend:** FastAPI (Python)
- **AI/ML:** OpenAI GPT-4o-mini / LangChain
- **OCR:** Pytesseract
- **PDF Generation:** ReportLab / Base64 conversion

## 🚀 Local Setup
1. **Backend:**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload