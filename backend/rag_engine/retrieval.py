from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

from app.models import LegalCitation

from .embeddings import HashEmbeddingFunction
from .ingest_stafford_act import COLLECTION_NAME, STAFFORD_ACT_URL, VECTOR_DIR


FALLBACK_CHUNKS = [
    {
        "id": "fallback-5121",
        "text": (
            "The Stafford Act provides an orderly and continuing means of assistance by the Federal "
            "Government to State and local governments in carrying out their responsibilities to "
            "alleviate the suffering and damage which result from disasters."
        ),
        "page": 1,
    },
    {
        "id": "fallback-5174",
        "text": (
            "Federal assistance to individuals and households may include financial assistance and, "
            "if necessary, direct services to respond to disaster-related necessary expenses and "
            "serious needs."
        ),
        "page": None,
    },
    {
        "id": "fallback-housing",
        "text": (
            "Disaster assistance may support housing needs, essential repairs, temporary housing, "
            "and other necessary expenses when caused by a major disaster."
        ),
        "page": None,
    },
]


def _collection():
    Path(VECTOR_DIR).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VECTOR_DIR), settings=Settings(anonymized_telemetry=False))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=HashEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    if collection.count() == 0:
        collection.upsert(
            ids=[chunk["id"] for chunk in FALLBACK_CHUNKS],
            documents=[chunk["text"] for chunk in FALLBACK_CHUNKS],
            metadatas=[
                {
                    "source": STAFFORD_ACT_URL,
                    "page": chunk["page"] or "",
                    "title": "Stafford Act bootstrap citation",
                }
                for chunk in FALLBACK_CHUNKS
            ],
        )
    return collection


def retrieve_relevant_clauses(query: str, limit: int = 4) -> list[LegalCitation]:
    collection = _collection()
    results = collection.query(query_texts=[query], n_results=limit)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    citations: list[LegalCitation] = []
    for document, metadata in zip(documents, metadatas):
        page_value = metadata.get("page")
        page = int(page_value) if str(page_value).isdigit() else None
        excerpt = " ".join(str(document).split())
        citations.append(
            LegalCitation(
                title=str(metadata.get("title") or "Stafford Act"),
                source=str(metadata.get("source") or STAFFORD_ACT_URL),
                page=page,
                excerpt=excerpt[:700],
            )
        )
    return citations
