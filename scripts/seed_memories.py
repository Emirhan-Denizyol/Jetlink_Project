import json
from pathlib import Path
import numpy as np

from src.memory.ltm_store import LTMStore
from src.embed.google_embed import embed_texts_google as embed_fn

DB = Path("data/memory.db")
SEEDS = Path("data/seeds.json")

def main():
    if not DB.exists():
        raise SystemExit("DB yok. Önce: python scripts/init_db.py")
    if not SEEDS.exists():
        raise SystemExit("data/seeds.json bulunamadı.")

    store = LTMStore(DB)
    seeds = json.loads(SEEDS.read_text(encoding="utf-8"))

    texts = [s["text"] for s in seeds]
    embs = embed_fn(texts)
    for s, e in zip(seeds, embs):
        store.insert_memory(
            user_id=s.get("user_id", "demo-user"),
            kind=s.get("kind", "note"),
            text=s["text"],
            embedding=e,
            source=s.get("source"),
            tags=s.get("tags"),
            expires_at=s.get("expires_at"),
        )
    print(f"✓ {len(seeds)} kayıt yüklendi.")

if __name__ == "__main__":
    main()
