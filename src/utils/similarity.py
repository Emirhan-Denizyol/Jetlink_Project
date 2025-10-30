from __future__ import annotations
import numpy as np
from typing import Tuple

def _as_2d(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[None, :]
    return x

def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    x = _as_2d(np.asarray(x))
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms = np.maximum(norms, eps)
    return x / norms

def cosine_similarity(a: np.ndarray, b: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """
    a: (N, D) veya (D,)
    b: (M, D) veya (D,)
    return: (N, M) cosine skor matrisi
    """
    A = l2_normalize(a, eps)
    B = l2_normalize(b, eps)
    return A @ B.T  # (N, M)

def top_k_similar(
    query: np.ndarray,
    keys: np.ndarray,
    k: int = 5
) -> Tuple[np.ndarray, np.ndarray]:
    """
    query: (D,) veya (1, D)
    keys: (N, D)
    return: (indices, scores) her ikisi de (k,)
    """
    sims = cosine_similarity(query, keys).ravel()  # (N,)
    if k <= 0:
        return np.array([], dtype=int), np.array([], dtype=np.float32)
    k = min(k, sims.shape[0])
    # argpartition ile O(N) seç, sonra skorla sırala
    idx = np.argpartition(-sims, kth=k-1)[:k]
    idx_sorted = idx[np.argsort(-sims[idx])]
    return idx_sorted.astype(int), sims[idx_sorted].astype(np.float32)
