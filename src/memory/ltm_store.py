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
        # FK desteği
        con.execute("PRAGMA foreign_keys = ON;")
        return con

    # ---------------- Helpers ----------------
    def _to_fts_and_prefix_query(self, text: str) -> str:
        """
        Serbest metni FTS5 için güvenli bir 'AND' + prefix aramasına çevirir.
        Örn: 'kahve süt' -> 'kahve* AND süt*'
        """
        tokens = []
        for raw in (text or "").strip().split():
            tok = re.sub(r"[^\wçğıöşüÇĞİÖŞÜ]+", "", raw, flags=re.UNICODE).lower()
            if tok:
                tokens.append(f"{tok}*")
        if not tokens:
            return ""
        return " AND ".join(tokens)

    def _prefetch_rows(
        self,
        user_id: str,
        fts_query: str,
        topn_prefilter: int,
        extra_where_sql: str = "",
        extra_params: Tuple[Any, ...] = (),
        now_ts_sql: str = "strftime('%s','now')",
    ) -> List[sqlite3.Row]:
        """
        FTS5 varsa onu kullan, yoksa doğrudan tablo üzerinden sırala.
        extra_where_sql boş olabilir; doluysa başında ' AND ' ile gelmelidir.
        """
        with self._connect() as con:
            if fts_query:
                cur = con.execute(
                    f"""
                    SELECT m.id, m.user_id, m.kind, m.text, m.embedding, m.source, m.tags, m.created_at, m.expires_at,
                           CAST({now_ts_sql} - strftime('%s', m.created_at) AS INTEGER) AS age_sec
                    FROM memories_fts f
                    JOIN memories m ON m.id = f.rowid
                    WHERE m.user_id = ?
                      AND memories_fts MATCH ?
                      {extra_where_sql}
                    LIMIT ?
                    """,
                    (user_id, fts_query, *extra_params, topn_prefilter),
                )
            else:
                cur = con.execute(
                    f"""
                    SELECT m.id, m.user_id, m.kind, m.text, m.embedding, m.source, m.tags, m.created_at, m.expires_at,
                           CAST({now_ts_sql} - strftime('%s', m.created_at) AS INTEGER) AS age_sec
                    FROM memories m
                    WHERE m.user_id = ?
                      {extra_where_sql}
                    ORDER BY m.id DESC
                    LIMIT ?
                    """,
                    (user_id, *extra_params, topn_prefilter),
                )
            return cur.fetchall()

    def _score_rows(
        self,
        rows: List[sqlite3.Row],
        query_text: str,
        embed_fn: Callable[[List[str]], np.ndarray],
        alpha: float,
        beta: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Cosine + Recency skorlarını hesaplar.
        """
        if not rows:
            return (np.array([]), np.array([]), np.array([]))

        q_emb = embed_fn([query_text])[0].astype(np.float32)
        mat = np.stack([np.frombuffer(r["embedding"], dtype=np.float32) for r in rows], axis=0)

        sims = cosine_similarity(q_emb, mat).ravel().astype(np.float32)
        age_days = np.array([max(r["age_sec"], 0) / 86400.0 for r in rows], dtype=np.float32)
        recency = 1.0 / (1.0 + np.log10(1.0 + age_days))
        score = alpha * sims + beta * recency
        return sims, recency, score

    def _normalize_tags(self, kind: str, tags: Optional[str]) -> Optional[str]:
        """
        - etiketleri virgül/boşlukla ayrılmış stringten listeye çevirir,
        - profile/fact için 'global' etiketini otomatik ekler,
        - tekilleştirip geri döndürür.
        """
        parts = []
        s = (tags or "").strip()
        if s:
            parts = [p.strip() for p in re.split(r"[,\s]+", s) if p.strip()]

        if kind in {"profile", "fact"} and "global" not in parts:
            parts.insert(0, "global")  # sohbetler arası hatırlama için

        # tekilleştir
        seen = []
        for p in parts:
            if p not in seen:
                seen.append(p)
        return ",".join(seen) if seen else None

    # ---------------- CRUD ----------------
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

    # ------------- General similarity helpers -------------
    def get_recent_memories(self, user_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        with self._connect() as con:
            cur = con.execute(
                """
                SELECT id, user_id, kind, text, embedding, source, tags, created_at, expires_at
                FROM memories
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (user_id, limit),
            )
            rows = cur.fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "kind": r["kind"],
                "text": r["text"],
                "embedding": np.frombuffer(r["embedding"], dtype=np.float32),
                "source": r["source"],
                "tags": r["tags"],
                "created_at": r["created_at"],
                "expires_at": r["expires_at"],
            })
        return out

    def find_most_similar(self, user_id: str, query_emb: np.ndarray, limit: int = 200) -> Tuple[Optional[int], float]:
        """
        Brute-force yakınlık: son 'limit' kayıttan en benzerini döndürür.
        """
        items = self.get_recent_memories(user_id, limit=limit)
        if not items:
            return None, -1.0
        mat = np.stack([it["embedding"] for it in items], axis=0)
        sims = cosine_similarity(query_emb.astype(np.float32), mat).ravel()
        j = int(np.argmax(sims))
        return items[j]["id"], float(sims[j])

    def upsert_if_novel(
        self,
        user_id: str,
        kind: str,
        text: str,
        embedding: np.ndarray,
        *,
        source: Optional[str] = None,
        tags: Optional[str] = None,
        expires_at: Optional[str] = None,
        similarity_threshold: float = 0.84,
        recent_limit: int = 200,
        merge_if_similar: bool = False,
    ) -> int:
        """
        Benzerlik eşiğine göre:
        - Eğer yakın benzer varsa:
            - merge_if_similar=True ise mevcut metni genişlet/güncelle,
            - aksi halde NO-OP (duplicate'dan kaçın).
        - Aksi halde yeni kayıt oluştur.
        Dönüş: kayıt id (mevcut/güncellenmiş veya yeni).
        Not: profile/fact için 'global' etiketi otomatik eklenir.
        """
        # Otomatik etiket normalizasyonu (global vb.)
        norm_tags = self._normalize_tags(kind, tags)

        sim_id, sim_val = self.find_most_similar(user_id, embedding, limit=recent_limit)
        if sim_id is not None and sim_val >= similarity_threshold:
            if merge_if_similar:
                old = self.get_memory(sim_id)
                if old:
                    # Basit birleştirme: farklıysa ekle
                    if text not in (old.text or ""):
                        new_text = (old.text + " | " + text) if old.text else text
                        self.update_memory_text(sim_id, new_text, embedding)
            return sim_id  # mevcut id

        # Yeni kayıt
        return self.insert_memory(
            user_id=user_id,
            kind=kind,
            text=text,
            embedding=embedding,
            source=source,
            tags=norm_tags,
            expires_at=expires_at,
        )

    # ---------------- Retrieval (eski API: global) ----------------
    def search(
        self,
        user_id: str,
        query_text: str,
        embed_fn: Callable[[List[str]], np.ndarray],
        topn_prefilter: int = 100,
        topk: int = 8,
        alpha: float = 0.9,
        beta: float = 0.1,
        now_ts_sql: str = "strftime('%s','now')"
    ) -> List[Dict[str, Any]]:
        """
        Geriye dönük uyumluluk için global arama.
        """
        fts_query = self._to_fts_and_prefix_query(query_text)
        rows = self._prefetch_rows(
            user_id=user_id,
            fts_query=fts_query,
            topn_prefilter=topn_prefilter,
            extra_where_sql="",
            extra_params=(),
            now_ts_sql=now_ts_sql,
        )
        if not rows:
            return []

        sims, recency, score = self._score_rows(rows, query_text, embed_fn, alpha, beta)
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
                "scope": "global",
            })
        return result

    # -------- Retrieval (yeni API: yerel + küresel hibrit) --------
    def search_scoped(
        self,
        user_id: str,
        query_text: str,
        embed_fn: Callable[[List[str]], np.ndarray],
        *,
        conv_id: Optional[int] = None,
        topn_prefilter: int = 150,
        topk_local: int = 4,
        topk_global: int = 4,
        w_local: float = 1.0,
        w_global: float = 1.0,
        alpha: float = 0.9,
        beta: float = 0.1,
        now_ts_sql: str = "strftime('%s','now')"
    ) -> List[Dict[str, Any]]:
        """
        Aynı sohbetten (yerel) ve tüm sohbetlerden (küresel) adayları çekip,
        ağırlıklı skorlama ile birleştirir.
        'Yerel' filtre: (tags LIKE '%conv:<id>%' OR source LIKE '%conv:<id>%')
        """
        fts_query = self._to_fts_and_prefix_query(query_text)

        def _fetch_hybrid(extra_where_sql: str, extra_params: Tuple[Any, ...]):
            # FTS + Recent birleşimi
            rows_fts = self._prefetch_rows(
                user_id=user_id,
                fts_query=fts_query,
                topn_prefilter=topn_prefilter // 2,
                extra_where_sql=extra_where_sql,
                extra_params=extra_params,
                now_ts_sql=now_ts_sql,
            ) if fts_query else []

            rows_recent = self._prefetch_rows(
                user_id=user_id,
                fts_query="",
                topn_prefilter=topn_prefilter,
                extra_where_sql=extra_where_sql,
                extra_params=extra_params,
                now_ts_sql=now_ts_sql,
            )

            # id bazlı tekilleştirme
            seen = set()
            merged = []
            for r in rows_fts + rows_recent:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                merged.append(r)
            return merged

        # Yerel satırlar
        local_rows: List[sqlite3.Row] = []
        if conv_id is not None:
            extra_where_local = " AND (m.tags LIKE ? OR m.source LIKE ?)"
            conv_token = f"%conv:{conv_id}%"
            local_rows = _fetch_hybrid(extra_where_local, (conv_token, conv_token))

        # Küresel satırlar (filtre yok)
        global_rows = _fetch_hybrid("", ())

        # Skorlama
        sims_l, rec_l, score_l = self._score_rows(local_rows, query_text, embed_fn, alpha, beta) if local_rows else (np.array([]), np.array([]), np.array([]))
        sims_g, rec_g, score_g = self._score_rows(global_rows, query_text, embed_fn, alpha, beta) if global_rows else (np.array([]), np.array([]), np.array([]))

        # Ağırlık uygula
        if score_l.size:
            score_l = w_local * score_l
        if score_g.size:
            score_g = w_global * score_g

        # En iyi k kayıtları topla
        def _top(rows, sims, rec, score, k, scope_name):
            if not rows or score.size == 0:
                return []
            k_eff = min(k, score.shape[0])
            idx = np.argpartition(-score, kth=k_eff-1)[:k_eff]
            order = idx[np.argsort(-score[idx])]
            out = []
            for i in order:
                r = rows[i]
                out.append({
                    "id": r["id"],
                    "user_id": r["user_id"],
                    "kind": r["kind"],
                    "text": r["text"],
                    "source": r["source"],
                    "tags": r["tags"],
                    "created_at": r["created_at"],
                    "expires_at": r["expires_at"],
                    "cosine": float(sims[i]),
                    "recency": float(rec[i]),
                    "score": float(score[i]),
                    "scope": scope_name,
                })
            return out

        local_top = _top(local_rows, sims_l, rec_l, score_l, topk_local, "local")
        global_top = _top(global_rows, sims_g, rec_g, score_g, topk_global, "global")

        # Birleştir (aynı id gelirse, yüksek skorlu olan kalsın)
        combined: Dict[int, Dict[str, Any]] = {}
        for item in (local_top + global_top):
            mid = item["id"]
            if (mid not in combined) or (item["score"] > combined[mid]["score"]):
                combined[mid] = item

        # Nihai sıralama
        final = sorted(combined.values(), key=lambda x: x["score"], reverse=True)
        return final
