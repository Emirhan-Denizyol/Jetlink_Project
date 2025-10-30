# scripts/init_db.py
import sqlite3
from pathlib import Path

DB_PATH = Path("data/memory.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

schema = r"""
PRAGMA journal_mode=WAL;

/* --- LTM mevcut tablolar (değiştirmiyoruz) --- */
CREATE TABLE IF NOT EXISTS memories (
  id INTEGER PRIMARY KEY,
  user_id TEXT NOT NULL,
  kind TEXT CHECK(kind IN ('preference','profile','fact','note')) NOT NULL,
  text TEXT NOT NULL,
  embedding BLOB NOT NULL,
  source TEXT,
  tags TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  expires_at TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
USING fts5(text, content='memories', content_rowid='id');

CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
  INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
  INSERT INTO memories_fts(memories_fts, rowid, text) VALUES('delete', old.id, old.text);
  INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
END;

/* --- Yeni: sohbet kalıcılığı --- */
CREATE TABLE IF NOT EXISTS conversations (
  id INTEGER PRIMARY KEY,
  user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  conv_id INTEGER NOT NULL,
  role TEXT CHECK(role IN ('user','assistant','system')) NOT NULL,
  content TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY(conv_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conv_id, id);
"""


with sqlite3.connect(DB_PATH) as con:
    con.executescript(schema)

print(f"✅ Database initialized at {DB_PATH.resolve()}")
