"""
memory_store.py

Vector-based conversation memory using ChromaDB.

Each memory item is stored as:
- document: "User: ...\nAssistant: ..."
- metadata: { "source": "conversation", "order_id": "...", "ticket_id": "...", ... }

You can:
- add_turn_to_memory(...)   -> store a new user+assistant pair
- add_custom_memory(...)    -> store any arbitrary text + metadata
- search_memory(query, ...) -> retrieve most relevant past memories for RAG
- clear_memory()            -> wipe the collection
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

# ==========================
# 1. Configuration
# ==========================

BASE_DIR = Path(__file__).resolve().parent

# Where to store Chroma DB on disk (can override via env var)
DB_DIR = Path(os.getenv("MEMORY_DB_DIR", BASE_DIR / "chroma_store"))
DB_DIR.mkdir(parents=True, exist_ok=True)

# Collection name (you can override via env var if you have multiple agents)
COLLECTION_NAME = os.getenv("MEMORY_COLLECTION_NAME", "support_memory")

# Embedding model for text -> vector
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

# Max number of results to retrieve
DEFAULT_TOP_K = int(os.getenv("MEMORY_TOP_K", "5"))

# ==========================
# 2. Init Chroma + Embeddings
# ==========================

# Persistent client: data lives under DB_DIR
_client = chromadb.PersistentClient(path=str(DB_DIR))

# Create or get the collection (cosine similarity)
_collection = _client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"},
)

# SentenceTransformer embedder
_embedder = SentenceTransformer(EMBED_MODEL_NAME)


def _embed_texts(texts: List[str]) -> List[List[float]]:
    """Convert a list of texts into embeddings."""
    vectors = _embedder.encode(texts, show_progress_bar=False)
    return [v.tolist() for v in vectors]


# ==========================
# 3. Public API
# ==========================

def add_turn_to_memory(
    user_message: str,
    assistant_message: str,
    order_id: Optional[str] = None,
    ticket_id: Optional[str] = None,
    issue_type: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Store a single conversation turn (user + assistant) as one vector document.

    Returns:
        The generated document ID in Chroma.
    """
    doc_id = f"turn_{uuid.uuid4().hex}"

    text = f"User: {user_message}\nAssistant: {assistant_message}"

    metadata: Dict[str, Any] = {
        "source": "conversation",
    }
    if order_id:
        metadata["order_id"] = str(order_id)
    if ticket_id:
        metadata["ticket_id"] = str(ticket_id)
    if issue_type:
        metadata["issue_type"] = str(issue_type)

    if extra_metadata:
        metadata.update(extra_metadata)

    embeddings = _embed_texts([text])

    _collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[metadata],
        embeddings=embeddings,
    )

    return doc_id


def add_custom_memory(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    doc_id: Optional[str] = None,
) -> str:
    """
    Store any arbitrary text + metadata as a memory document.

    Useful for:
    - Ticket summaries
    - Important notes
    - Per-ticket or per-user context
    """
    if doc_id is None:
        doc_id = f"mem_{uuid.uuid4().hex}"

    base_metadata: Dict[str, Any] = {"source": "custom"}
    if metadata:
        base_metadata.update(metadata)

    embeddings = _embed_texts([text])

    _collection.add(
        ids=[doc_id],
        documents=[text],
        metadatas=[base_metadata],
        embeddings=embeddings,
    )

    return doc_id


def search_memory(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    where: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Semantic search over the conversation memory.

    Returns:
        [
          {
            "id": ...,
            "document": ...,
            "metadata": {...},
            "distance": 0.12
          },
          ...
        ]
    """
    if not query.strip():
        return []

    query_embedding = _embed_texts([query])[0]

    res = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where,
    )

    ids = res.get("ids", [[]])[0]
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    distances = res.get("distances", [[]])[0]

    results: List[Dict[str, Any]] = []
    for i, doc_id in enumerate(ids):
        results.append(
            {
                "id": doc_id,
                "document": docs[i],
                "metadata": metas[i],
                "distance": float(distances[i]),
            }
        )
    return results


def count_memory() -> int:
    """Return how many documents are stored in the memory collection."""
    return _collection.count()


def clear_memory() -> None:
    """Delete ALL documents from the memory collection."""
    _collection.delete(where={})


def delete_by_metadata(filter_metadata: Dict[str, Any]) -> None:
    """
    Delete documents that match a metadata filter, e.g.:

        delete_by_metadata({"ticket_id": "TKT-1234"})
    """
    _collection.delete(where=filter_metadata)
