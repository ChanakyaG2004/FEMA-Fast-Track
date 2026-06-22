# FEMA Fast-Track Backend

Local FastAPI service for claim intake, schema validation, Stafford Act-aligned phrasing, RAG citations, evidence extraction, skeptical review, and PDF generation.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-local.txt
python -m rag_engine.ingest_stafford_act --reset
uvicorn app.main:app --reload --port 8000
```

The RAG index downloads FEMA's official Stafford Act PDF from:

```text
https://www.fema.gov/sites/default/files/documents/fema_stafford_act_2021_vol1.pdf
```

It stores only legal reference chunks in `rag_engine/chroma_db`. Claim text and uploaded evidence are processed in memory and are not written to a persistent database.

Image OCR uses `pytesseract`, which requires the system Tesseract binary to be installed. PDF text extraction works with the Python dependencies alone.

By default the service uses deterministic local extraction and local hash embeddings. To enable OpenAI extraction/red-team review, set:

```bash
export ENABLE_OPENAI=1
export OPENAI_API_KEY=...
export OPENAI_MODEL=gpt-4o-mini
```

The system prompt instructs the model not to hallucinate legal codes and to refuse illegal or fraudulent requests.

## Vercel deployment

The frontend calls `/api/analyze-claim`; Vite's development proxy only exists on
your computer. This repository now includes a Vercel Python function at
`api/index.py` and routing in `vercel.json`, so deploy it as **one Vercel
project with the repository root as its Root Directory**. Do not set the Root
Directory to `frontend`, because Vercel would then omit the API function and
backend package.

In Vercel, redeploy after changing the Root Directory. The deployment should
then return `{"status":"ok"}` at `/api/health` and accept POST requests at
`/api/analyze-claim`.

The serverless API uses bundled Stafford Act fallback references rather than a
persistent Chroma database, since Vercel function storage is ephemeral. Local
and long-running deployments retain the Chroma retrieval behavior through
`requirements-local.txt`.

If you host the FastAPI backend separately instead, set `VITE_API_BASE_URL` in
the Vercel project's environment variables to that backend's public URL and
redeploy. Copy `.env.example` for the variable names; never put
`OPENAI_API_KEY` in a `VITE_` variable.
