"""
rag_utils.py

RAG over:
- Policy documents in ./data (refund, shipping, cancellation, FAQ)
- Conversation memory stored in ChromaDB (via memory_store)

Uses Groq via LiteLLM. Make sure GROQ_API_KEY and MODEL_NAME
are set as environment variables (MODEL_NAME is optional).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from sentence_transformers import SentenceTransformer
import litellm

from memory_store import search_memory

# ==========================
# Config / Paths
# ==========================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SYSTEM_PROMPT_PATH = BASE_DIR / "system_prompt.txt"

EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
MODEL_NAME = os.getenv("MODEL_NAME", "groq/llama-3.1-70b-versatile")

# LiteLLM will pick up GROQ_API_KEY from env
# e.g. GROQ_API_KEY = gsk_xxx in HF Secrets or .env

# ==========================
# Load policy docs + embed them once
# ==========================

_embedder = SentenceTransformer(EMBED_MODEL_NAME)

_policy_docs: List[Dict[str, Any]] = []
for path in sorted(DATA_DIR.glob("*.txt")):
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        text = ""
    _policy_docs.append(
        {
            "filename": path.name,
            "text": text,
        }
    )

if _policy_docs:
    policy_texts = [p["text"] or "" for p in _policy_docs]
    _policy_embeddings = _embedder.encode(policy_texts, show_progress_bar=False)
    _policy_embeddings = np.array(_policy_embeddings, dtype="float32")
else:
    _policy_embeddings = np.zeros((0, 384), dtype="float32")  # safe default


def _embed_query(text: str) -> np.ndarray:
    vec = _embedder.encode([text], show_progress_bar=False)[0]
    return np.array(vec, dtype="float32")


def retrieve_policy_snippets(query: str, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Simple cosine similarity over policy docs.
    Returns top_k docs with highest similarity.
    """
    if _policy_embeddings.shape[0] == 0:
        return []

    q = _embed_query(query)  # (d,)
    docs_mat = _policy_embeddings  # (N, d)

    # cosine similarity
    q_norm = np.linalg.norm(q) + 1e-8
    docs_norm = np.linalg.norm(docs_mat, axis=1) + 1e-8
    sims = (docs_mat @ q) / (docs_norm * q_norm)

    top_idx = np.argsort(-sims)[:top_k]
    results: List[Dict[str, Any]] = []
    for idx in top_idx:
        d = _policy_docs[int(idx)]
        results.append(
            {
                "filename": d["filename"],
                "text": d["text"],
                "score": float(sims[idx]),
            }
        )
    return results


def get_memory_context(user_message: str, top_k: int = 5) -> str:
    """
    Query Chroma for semantically relevant conversation memory.
    Returns a formatted text block.
    """
    hits = search_memory(user_message, top_k=top_k)
    if not hits:
        return ""

    snippets = []
    for h in hits:
        doc = h["document"]
        meta = h.get("metadata", {})
        ticket_id = meta.get("ticket_id")
        order_id = meta.get("order_id")
        label_parts = []
        if ticket_id:
            label_parts.append(f"ticket={ticket_id}")
        if order_id:
            label_parts.append(f"order={order_id}")
        label = " ".join(label_parts)
        if label:
            snippets.append(f"[Past memory ({label})]\n{doc}")
        else:
            snippets.append(f"[Past memory]\n{doc}")

    return "\n\n---\n\n".join(snippets)


def answer_with_rag(user_message: str) -> Dict[str, Any]:
    """
    Combine:
    - Policy RAG
    - Vector memory from Chroma
    And ask the LLM to answer.

    Returns:
        {
          "answer": str,
          "context": str
        }
    """
    # 1) Policy docs
    policy_snippets = retrieve_policy_snippets(user_message, top_k=2)
    policy_context = ""
    if policy_snippets:
        joined = "\n\n---\n\n".join(
            f"[{s['filename']}]\n{s['text']}"
            for s in policy_snippets
            if s["text"].strip()
        )
        policy_context = joined

    # 2) Conversation memory from Chroma
    memory_context = get_memory_context(user_message, top_k=5)

    # 3) Build context block
    context_parts = []
    if policy_context:
        context_parts.append("Policy documents:\n" + policy_context)
    if memory_context:
        context_parts.append("Relevant past conversation:\n" + memory_context)

    context_block = "\n\n====\n\n".join(context_parts) if context_parts else ""

    # 4) System prompt
    try:
        system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        system_prompt = (
            "You are a helpful, policy-grounded customer support assistant. "
            "If you are unsure, say you are not sure."
        )

    # 5) Messages for LLM
    messages = [
        {
            "role": "system",
            "content": (
                system_prompt
                + "\n\n"
                "You have two sources of context:\n"
                "1) Policy documents (refund, shipping, cancellation, login).\n"
                "2) Conversation memory (past user–assistant messages) from a vector store.\n"
                "- Use policy docs for exact rules.\n"
                "- Use memory for recalling past interactions and tickets.\n"
                "- If something is not covered, say you are not sure.\n"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Context (may be empty):\n{context_block}\n\n"
                f"Customer message:\n{user_message}\n\n"
                "Reply as a friendly, concise support agent in 3–6 short sentences."
            ),
        },
    ]

    resp = litellm.completion(
        model=MODEL_NAME,
        messages=messages,
    )
    answer = resp["choices"][0]["message"]["content"]

    return {
        "answer": answer,
        "context": context_block,
    }
