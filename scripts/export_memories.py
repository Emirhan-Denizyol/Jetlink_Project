import json
from pathlib import Path
import sqlite3
import numpy as np

DB = Path("data/memory.db")
OUT = Path("data/memories_export.json")

def main():
    if not DB.exists():
        raise SystemExit("DB yok. Önce: python scripts/init_db.py")
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.execute("SELECT id,user_id,kind,text,source,tags,created_at,expires_at,embedding FROM memories ORDER BY id")
    rows = cur.fetchall()
    data = []
    for r in rows:
        emb = np.frombuffer(r["embedding"], dtype=np.float32).tolist()
        item = {k: r[k] for k in r.keys() if k != "embedding"}
        item["embedding"] = emb
        data.append(item)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✓ {len(data)} kayıt {OUT} dosyasına yazıldı.")

if __name__ == "__main__":
    main()
