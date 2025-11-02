import sqlite3
from pathlib import Path

DB = Path("data/memory.db")
if not DB.exists():
    raise SystemExit("⚠️ DB yok. Önce scripts/init_db.py çalıştırın.")

with sqlite3.connect(DB) as con:
    con.execute("PRAGMA foreign_keys = ON;")
    cur = con.cursor()

    # 1) Tablolardaki içerikleri sil
    cur.executescript("""
        DELETE FROM messages;
        DELETE FROM conversations;
        DELETE FROM memories;
    """)

    # 2) FTS varsa temizle
    try:
        cur.execute("DELETE FROM memories_fts;")
    except sqlite3.OperationalError:
        pass  # FTS tablosu yoksa atla

    # 3) sqlite_sequence varsa temizle (AUTOINCREMENT sayacı)
    try:
        cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('messages','conversations','memories');")
    except sqlite3.OperationalError:
        pass  # tablo yoksa sessizce geç

# 4) Diski toparla
with sqlite3.connect(DB) as con:
    con.execute("VACUUM;")

print("✅ DB reset tamamlandı (şema korundu, içerik sıfırlandı).")
