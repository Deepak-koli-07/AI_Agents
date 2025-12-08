from pathlib import Path
import os
import numpy as np
from sentence_transformers import SentenceTransformer
import litellm


from dotenv import load_dotenv
load_dotenv()

GROQ_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "groq/llama-3.1-70b-versatile")

litellm.api_key = GROQ_KEY

DATA_DIR = Path("data")
SYSTEM_PROMPT_PATH = Path("system_prompt.txt")


_EMBED_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

DOCS = []          
EMB_MATRIX = None  


def build_policy_index():
    global DOCS, EMB_MATRIX

    docs = []
    for fname in ["refund_policy.txt", "shipping_policy.txt",
                  "cancellation_policy.txt", "support_faq.txt"]:
        path = DATA_DIR / fname
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            if text:
                docs.append({"filename": fname, "text": text})

    if not docs:
        DOCS = []
        EMB_MATRIX = None
        return

    texts = [d["text"] for d in docs]
    emb = _EMBED_MODEL.encode(texts, convert_to_numpy=True, normalize_embeddings=True)

    DOCS = docs
    EMB_MATRIX = emb


build_policy_index()  


def _embed(text: str) -> np.ndarray:
    return _EMBED_MODEL.encode([text], convert_to_numpy=True, normalize_embeddings=True)[0]


def retrieve_policy_snippets(query: str, top_k: int = 2):
    if not DOCS or EMB_MATRIX is None:
        return []

    q_emb = _embed(query)
    scores = (EMB_MATRIX @ q_emb)  
    idx = np.argsort(scores)[::-1][:top_k]

    results = []
    for i in idx:
        results.append(
            {
                "filename": DOCS[i]["filename"],
                "text": DOCS[i]["text"],
                "score": float(scores[i]),
            }
        )
    return results


def answer_with_rag(user_message: str) -> dict:
    """
    Returns {"answer": str, "context": str}
    """
    snippets = retrieve_policy_snippets(user_message, top_k=2)

    context_text = ""
    if snippets:
        joined = "\n\n---\n\n".join(
            f"[{s['filename']}]\n{s['text']}" for s in snippets
        )
        context_text = joined

    system_prompt = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")

    messages = [
        {
            "role": "system",
            "content": (
                system_prompt
                + "\n\nRules:\n"
                  "- Use ONLY the policy text provided in context when talking about policies.\n"
                  "- Do NOT mention file names, searching or internal steps.\n"
                  "- Answer like a human support agent in 3–6 short sentences.\n"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Customer message:\n{user_message}\n\n"
                f"Policy context:\n{context_text}\n\n"
                "Based ONLY on this context, reply to the customer."
            ),
        },
    ]

    resp = litellm.completion(
        model=MODEL_NAME,
        messages=messages,
    )
    answer = resp["choices"][0]["message"]["content"]

    return {"answer": answer, "context": context_text}
