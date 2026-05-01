# FEMA Fast-Track Backend

Local FastAPI service for claim intake, schema validation, Stafford Act-aligned phrasing, RAG citations, evidence extraction, skeptical review, and PDF generation.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
