from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional

DB_PATH = Path("data/memory.db")

class ChatStore:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError("DB yok. scripts/init_db.py çalıştırın.")

    def _con(self):
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    # --- Conversations ---
    def list_conversations(self, user_id: str) -> List[Dict]:
        with self._con() as con:
            cur = con.execute("""
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE user_id=?
                ORDER BY updated_at DESC, id DESC
            """, (user_id,))
            return [dict(r) for r in cur.fetchall()]

    def create_conversation(self, user_id: str, title: str) -> int:
        with self._con() as con:
            cur = con.execute("""
                INSERT INTO conversations (user_id, title)
                VALUES (?, ?)
            """, (user_id, title))
            return int(cur.lastrowid)

    def rename_conversation(self, conv_id: int, new_title: str) -> None:
        with self._con() as con:
            con.execute("""
                UPDATE conversations SET title=?, updated_at=datetime('now') WHERE id=?
            """, (new_title, conv_id))

    def delete_conversation(self, conv_id: int) -> None:
        with self._con() as con:
            con.execute("DELETE FROM conversations WHERE id=?", (conv_id,))

    # --- Messages ---
    def add_message(self, conv_id: int, role: str, content: str) -> int:
        with self._con() as con:
            cur = con.execute("""
                INSERT INTO messages (conv_id, role, content)
                VALUES (?, ?, ?)
            """, (conv_id, role, content))
            con.execute("UPDATE conversations SET updated_at=datetime('now') WHERE id=?", (conv_id,))
            return int(cur.lastrowid)

    def get_messages(self, conv_id: int, limit: Optional[int] = None) -> List[Dict]:
        q = "SELECT role, content FROM messages WHERE conv_id=? ORDER BY id ASC"
        if limit:
            q += f" LIMIT {int(limit)}"
        with self._con() as con:
            cur = con.execute(q, (conv_id,))
            return [dict(r) for r in cur.fetchall()]
