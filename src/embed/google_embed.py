from __future__ import annotations
from typing import List
import numpy as np
import google.generativeai as genai
from src.config import GOOGLE_API_KEY, EMBED_MODEL

def embed_texts_google(texts: List[str]) -> np.ndarray:
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is empty")
    genai.configure(api_key=GOOGLE_API_KEY)
    resp = genai.embed_content(model=EMBED_MODEL, content=texts)
    # Tek/çoklu formatı normalize et
    if isinstance(resp, dict) and "embedding" in resp:
        vecs = [resp["embedding"]]
    else:
        vecs = [r["embedding"] for r in resp["embeddings"]]
    arr = np.array(vecs, dtype=np.float32)
    # satır-normalizasyon (cosine için güvenli)
    norms = np.linalg.norm(arr, axis=1, keepdims=True) + 1e-12
    return (arr / norms).astype(np.float32)
