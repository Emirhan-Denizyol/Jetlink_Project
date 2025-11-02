from pathlib import Path
import sqlite3

DB = Path("data/memory.db")
with sqlite3.connect(DB) as con:
    con.row_factory = sqlite3.Row
    cur = con.execute("""
        SELECT id, text, created_at
        FROM memories
        WHERE user_id='demo-user' AND kind='fact' AND text LIKE '%Jetlink%'
        ORDER BY id DESC LIMIT 1
    """)
    r = cur.fetchone()
    if r:
        print(f"ID={r['id']} | {r['created_at']} | {r['text']}")
    else:
        print("Kayıt yok.")
