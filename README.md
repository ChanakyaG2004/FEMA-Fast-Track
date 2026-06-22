# FEMA Fast-Track

## Live website

https://fema-fast-track.vercel.app/

## Inspiration

Disaster relief paperwork can be confusing, especially when people are already dealing with stressful situations. Many FEMA applicants are denied or delayed because of missing documentation, ownership proof issues, application mistakes, or implete evidence, which can prevent people from receiving assistance unless they correct or appeal their claim.

A 2025 report cited by The Washington Post said about 38% of FEMA Individual Assistance applications were rejected from fiscal years 2020-2023, and earlier years had denial rates as high as 45%. Source: https://www.washingtonpost.com/dc-md-va/2025/07/23/maryland-fema-aid-trump/

I wanted to build an application that could help users organize FEMA-related claim information, review supporting evidence, and generate a clearer summary using AI and retrieval-based legal references.

This project was also a way for me to build a practical full-stack AI application that combines document processing, RAG, backend APIs, safer AI prompting, and report generation.

## Very simple high level overview

```text
User Claim Input + Uploaded Evidence
    ↓
FastAPI Backend
    ↓
Schema Validation
    ↓
Evidence Extraction
    ↓
Stafford Act RAG Retrieval
    ↓
AI / Deterministic Claim Review
    ↓
Skeptical Review
    ↓
Structured PDF Summary
    ↓
Vercel Deployment
```

## What the app does

FEMA Fast-Track is an AI-assisted claim review tool that helps users organize disaster relief claim information. The app takes in claim details and uploaded evidence, extracts relevant information, retrieves Stafford Act references, reviews the claim, and generates a structured PDF summary.

The goal is not to replace FEMA, legal advice, or official disaster assistance review. The goal is to make complex claim information easier to understand and organize.

## Features

* Claim intake form for disaster relief information
* Schema validation for structured claim data
* Stafford Act-aligned phrasing
* Evidence extraction from uploaded files
* PDF text extraction using Python dependencies
* Image OCR support with `pytesseract`
* RAG citations from Stafford Act reference chunks
* Local deterministic extraction mode
* Local hash embeddings by default
* Optional OpenAI-powered extraction and skeptical review
* Hallucination-resistant prompting for legal references
* Refusal behavior for illegal or fraudulent requests
* Structured PDF report generation
* FastAPI backend for claim analysis
* Vercel API route support for deployment

## Core Stack

* Python for backend logic, document processing, and PDF generation
* FastAPI for the claim analysis API
* React / Vite for the frontend
* RAG pipeline for Stafford Act reference retrieval
* ChromaDB for local retrieval storage
* OpenAI API for optional AI extraction and red-team review
* `pytesseract` for image OCR
* PDF text extraction for uploaded document evidence
* Vercel for deployment
* Environment variables for secure API configuration

## RAG and Stafford Act References

The RAG index downloads FEMA's official Stafford Act PDF from:

```text
https://www.fema.gov/sites/default/files/documents/fema_stafford_act_2021_vol1.pdf
```

The app stores only legal reference chunks in `rag_engine/chroma_db`. Claim text and uploaded evidence are processed in memory and are not written to a persistent database.

This design keeps user-submitted claim information separate from the stored legal reference index.

## Evidence Extraction

The app supports evidence extraction from uploaded files. PDF text extraction works with the Python dependencies alone.

Image OCR uses `pytesseract`, which requires the system Tesseract binary to be installed separately.

## AI Review

By default, the service uses deterministic local extraction and local hash embeddings. OpenAI-powered extraction and skeptical review can be enabled through environment variables.

```bash
export ENABLE_OPENAI=1
export OPENAI_API_KEY=your_api_key_here
export OPENAI_MODEL=gpt-4o-mini
```

When OpenAI mode is enabled, the app can perform AI-assisted extraction and skeptical review. The system prompt instructs the model not to hallucinate legal codes and to refuse illegal or fraudulent requests.

## API

The backend exposes claim analysis through FastAPI. The main endpoint accepts claim information and evidence, processes the request, retrieves relevant Stafford Act references, and returns a structured analysis.

```text
POST /api/analyze-claim
```

There is also a health check endpoint for deployment testing.

```text
GET /api/health
```

## Frontend

The frontend provides a simple interface for entering claim details and submitting evidence. It connects to the backend API, displays the claim review results, and supports report generation.

The frontend calls:

```text
/api/analyze-claim
```

The goal of the interface is to make a technical AI/RAG workflow feel understandable and usable for a normal person.

## Running Locally

Clone the repository:

```bash
git clone https://github.com/ChanakyaG2004/FEMA-Fast-Track.git
cd FEMA-Fast-Track
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install local dependencies:

```bash
pip install -r requirements-local.txt
```

Ingest the Stafford Act references:

```bash
python -m rag_engine.ingest_stafford_act --reset
```

Run the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

## Vercel Deployment

This repository includes a Vercel Python function at:

```text
api/index.py
```

and routing in:

```text
vercel.json
```

Deploy the project as one Vercel project with the repository root as the Root Directory. Do not set the Root Directory to `frontend`, because Vercel would omit the API function and backend package.

After deployment, the app should return:

```text
{"status":"ok"}
```

at:

```text
/api/health
```

and accept POST requests at:

```text
/api/analyze-claim
```

The Vite development proxy only works on your local computer, so the deployed frontend needs the Vercel API route or a separate backend URL.

The serverless API uses bundled Stafford Act fallback references instead of a persistent Chroma database because Vercel function storage is ephemeral. Local and long-running deployments retain the Chroma retrieval behavior through `requirements-local.txt`.

If the FastAPI backend is hosted separately, set `VITE_API_BASE_URL` in the Vercel project's environment variables to that backend's public URL and redeploy.

Copy `.env.example` for the variable names. Never put `OPENAI_API_KEY` in a `VITE_` variable.

## Project Structure

```text
FEMA-Fast-Track/
  ├── README.md
  ├── requirements-local.txt
  ├── vercel.json
  ├── api/
  │   └── index.py
  ├── app/
  │   └── main.py
  ├── rag_engine/
  │   ├── ingest_stafford_act.py
  │   └── chroma_db/
  ├── frontend/
  │   ├── package.json
  │   ├── vite.config.js
  │   └── src/
  └── .env.example
```

## Limitations

* This project is not legal advice
* The app does not submit claims to FEMA
* The app does not determine official FEMA eligibility
* The quality of the review depends on the information and evidence provided by the user
* OCR requires the system Tesseract binary to be installed
* Vercel serverless deployment uses bundled Stafford Act fallback references instead of persistent Chroma storage
* Local and long-running deployments are better suited for persistent Chroma retrieval
* The app is meant for claim organization and analysis, not official eligibility determination

## Future improvements

The main thing I would want to add for future improvements would be AI reasoning for the answers. For example, even after giving an explanation about when and where the disaster happens, the question would still ask when the disaster happened. If there was some extra AI reasoning, it would read the user input and understand that the answer was already given and the extra question is unnecessary.

## What I learned

This project helped me understand how to build a full-stack AI application that connects user input, document processing, retrieval augmented generation, backend APIs, and PDF generation.

I learned more about designing safer AI workflows, especially when working with legal or government-related information. I also gained experience with FastAPI, Vercel deployment, RAG pipelines, OCR, environment configuration, and building applications that turn complex documents into more understandable outputs.

## Quick disclaimer

This project is for educational and organizational purposes only. It is not legal advice, financial advice, or an official FEMA tool. It does not determine eligibility, submit claims, or replace guidance from FEMA or a qualified professional.

Thanks for reading!!!
