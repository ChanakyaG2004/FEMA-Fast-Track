from __future__ import annotations

import argparse
import os
import urllib.request
from pathlib import Path

import chromadb
from chromadb.config import Settings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .embeddings import HashEmbeddingFunction


STAFFORD_ACT_URL = "https://www.fema.gov/sites/default/files/documents/fema_stafford_act_2021_vol1.pdf"
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VECTOR_DIR = BASE_DIR / "chroma_db"
PDF_PATH = DATA_DIR / "stafford_act.pdf"
COLLECTION_NAME = "stafford_act"


def download_stafford_act(url: str = STAFFORD_ACT_URL, destination: Path = PDF_PATH) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 100_000:
        return destination
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FEMA-Fast-Track local RAG indexer (contact: local-dev)",
            "Accept": "application/pdf,*/*",
        },
    )
    with urllib.request.urlopen(request) as response:
        destination.write_bytes(response.read())
    return destination


def ingest_stafford_act(pdf_path: Path = PDF_PATH, reset: bool = False) -> int:
    if not pdf_path.exists():
        download_stafford_act(destination=pdf_path)

    loader = PyPDFLoader(str(pdf_path))
    pages = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=180)
    chunks = splitter.split_documents(pages)

    client = chromadb.PersistentClient(path=str(VECTOR_DIR), settings=Settings(anonymized_telemetry=False))
    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=HashEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )

    ids: list[str] = []
    docs: list[str] = []
    metadatas: list[dict[str, str | int]] = []
    for index, chunk in enumerate(chunks):
        text = " ".join(chunk.page_content.split())
        if len(text) < 80:
            continue
        ids.append(f"stafford-{index}")
        docs.append(text)
        metadatas.append(
            {
                "source": STAFFORD_ACT_URL,
                "page": int(chunk.metadata.get("page", 0)) + 1,
                "title": "Robert T. Stafford Disaster Relief and Emergency Assistance Act",
            }
        )

    if ids:
        collection.upsert(ids=ids, documents=docs, metadatas=metadatas)
    return len(ids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and index the Stafford Act into local ChromaDB.")
    parser.add_argument("--reset", action="store_true", help="Delete and rebuild the collection.")
    parser.add_argument("--pdf", default=os.getenv("STAFFORD_ACT_PDF", str(PDF_PATH)), help="Local PDF path to ingest.")
    args = parser.parse_args()
    count = ingest_stafford_act(Path(args.pdf), reset=args.reset)
    print(f"Indexed {count} Stafford Act chunks into {VECTOR_DIR}")


if __name__ == "__main__":
    main()
