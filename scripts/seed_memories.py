import json
from pathlib import Path
import numpy as np

from src.memory.ltm_store import LTMStore
from src.embed.google_embed import embed_texts_google as embed_fn

DB = Path("data/memory.db")
SEEDS = Path("data/seeds.json")

def _merge_tags(existing: str | None, extra: str | None) -> str | None:
    if not existing and not extra:
        return None
    parts = []
    if existing:
        parts.append(existing)
    if extra:
        parts.append(extra)
    # Basit birleştirme; aynı etiket varsa bırakabilir (sorun değil)
    return ", ".join(p for p in parts if p.strip())

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
        user_id = s.get("user_id", "demo-user")
        kind = s.get("kind", "note")
        text = s["text"]
        source = s.get("source")
        tags = s.get("tags")
        expires_at = s.get("expires_at")

        # Eğer seed içinde conv_id verildiyse, otomatik olarak conv:<id> etiketi ekle
        conv_id = s.get("conv_id")
        conv_tag = f"conv:{conv_id}" if conv_id is not None else None
        tags_final = _merge_tags(tags, conv_tag)

        store.insert_memory(
            user_id=user_id,
            kind=kind,
            text=text,
            embedding=e,
            source=source,
            tags=tags_final,
            expires_at=expires_at,
        )

    print(f"✓ {len(seeds)} kayıt yüklendi.")

if __name__ == "__main__":
    main()
