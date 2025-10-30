# src/memory/ltm_store.py
from __future__ import annotations
import sqlite3
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Dict, Any
import numpy as np

from src.utils.similarity import cosine_similarity

DB_PATH = Path("data/memory.db")

@dataclass
class Memory:
    id: int
    user_id: str
    kind: str
    text: str
    embedding: np.ndarray
    source: Optional[str]
    tags: Optional[str]
    created_at: str
    expires_at: Optional[str]

def _row_to_memory(row: Tuple[Any, ...]) -> Memory:
    # row = (id,user_id,kind,text,embedding,source,tags,created_at,expires_at)
    emb = np.frombuffer(row[4], dtype=np.float32)
    return Memory(
        id=row[0],
        user_id=row[1],
        kind=row[2],
        text=row[3],
        embedding=emb,
        source=row[5],
        tags=row[6],
        created_at=row[7],
        expires_at=row[8],
    )

class LTMStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Database not found at {self.db_path}. Run scripts/init_db.py first."
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    # --- Helpers ---
    def _to_fts_and_prefix_query(self, text: str) -> str:
        """
        Serbest metni FTS5 için güvenli bir 'AND' + prefix aramasına çevirir.
        Örn: 'kahve süt' -> 'kahve* AND süt*'
        Noktalama ve özel karakterler temizlenir; boşluklar token sınırı kabul edilir.
        """
        tokens = []
        for raw in text.strip().split():
            # Türkçe karakterleri koruyarak noktalama/özel karakterleri temizle
            tok = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]+", "", raw, flags=re.UNICODE).lower()
            if tok:
                tokens.append(f"{tok}*")
        if not tokens:
            return ""
        return " AND ".join(tokens)

    # ---------- CRUD ----------
    def insert_memory(
        self,
        user_id: str,
        kind: str,
        text: str,
        embedding: np.ndarray,
        source: Optional[str] = None,
        tags: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> int:
        emb_bytes = np.asarray(embedding, dtype=np.float32).tobytes()
        with self._connect() as con:
            cur = con.execute(
                """
                INSERT INTO memories (user_id, kind, text, embedding, source, tags, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, kind, text, emb_bytes, source, tags, expires_at),
            )
            return int(cur.lastrowid)

    def get_memory(self, mem_id: int) -> Optional[Memory]:
        with self._connect() as con:
            cur = con.execute(
                "SELECT id,user_id,kind,text,embedding,source,tags,created_at,expires_at FROM memories WHERE id=?",
                (mem_id,),
            )
            row = cur.fetchone()
        return _row_to_memory(tuple(row)) if row else None

    def update_memory_text(self, mem_id: int, new_text: str, new_embedding: np.ndarray) -> None:
        emb_bytes = np.asarray(new_embedding, dtype=np.float32).tobytes()
        with self._connect() as con:
            con.execute(
                "UPDATE memories SET text=?, embedding=? WHERE id=?",
                (new_text, emb_bytes, mem_id),
            )

    def delete_memory(self, mem_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM memories WHERE id=?", (mem_id,))

    # ---------- Retrieval ----------
    def search(
        self,
        user_id: str,
        query_text: str,
        embed_fn: Callable[[List[str]], np.ndarray],
        topn_prefilter: int = 100,
        topk: int = 8,
        alpha: float = 0.9,   # cosine ağırlığı
        beta: float = 0.1,    # recency ağırlığı
        now_ts_sql: str = "strftime('%s','now')"  # sqlite epoch seconds
    ) -> List[Dict[str, Any]]:
        """
        1) FTS5 ile adayları getir (user_id filtresi ile)
        2) Query embedding hesapla
        3) Cosine similarity ile skorla, üzerine recency bonus ekle
        4) Top-k döndür
        """
        with self._connect() as con:
            fts_query = self._to_fts_and_prefix_query(query_text)
            if fts_query:
                cur = con.execute(
                    f"""
                    SELECT m.id, m.user_id, m.kind, m.text, m.embedding, m.source, m.tags, m.created_at, m.expires_at,
                           CAST({now_ts_sql} - strftime('%s', m.created_at) AS INTEGER) AS age_sec
                    FROM memories_fts f
                    JOIN memories m ON m.id = f.rowid
                    WHERE m.user_id = ?
                      AND memories_fts MATCH ?
                    LIMIT ?
                    """,
                    (user_id, fts_query, topn_prefilter),
                )
            else:
                cur = con.execute(
                    f"""
                    SELECT m.id, m.user_id, m.kind, m.text, m.embedding, m.source, m.tags, m.created_at, m.expires_at,
                           CAST({now_ts_sql} - strftime('%s', m.created_at) AS INTEGER) AS age_sec
                    FROM memories m
                    WHERE m.user_id = ?
                    ORDER BY m.id DESC
                    LIMIT ?
                    """,
                    (user_id, topn_prefilter),
                )
            rows = cur.fetchall()

        if not rows:
            return []

        # 2) Embedding hesapları
        q_emb = embed_fn([query_text])[0].astype(np.float32)
        mat = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows], axis=0)

        # 3) Cosine + Recency
        sims = cosine_similarity(q_emb, mat).ravel()
        # recency decay: 1 / (1 + log10(1 + age_days))
        age_days = np.array([max(r["age_sec"], 0) / 86400.0 for r in rows], dtype=np.float32)
        recency = 1.0 / (1.0 + np.log10(1.0 + age_days))
        score = alpha * sims + beta * recency

        # 4) Top-k
        k = min(topk, score.shape[0])
        top_idx = np.argpartition(-score, kth=k-1)[:k]
        order = top_idx[np.argsort(-score[top_idx])]
        result = []
        for i in order:
            r = rows[i]
            result.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "kind": r["kind"],
                "text": r["text"],
                "source": r["source"],
                "tags": r["tags"],
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
                "cosine": float(sims[i]),
                "recency": float(recency[i]),
                "score": float(score[i]),
            })
        return result
