# tests/test_ltm_store.py
import os
import numpy as np
from pathlib import Path
from src.memory.ltm_store import LTMStore
from src.memory.retrieval import retrieve_context

DB_FILE = Path("data/memory.db")

def fake_embed(texts):
    # Deterministik basit vektör: 128 boyutlu, hash tabanlı
    vecs = []
    for t in texts:
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        v = rng.normal(size=128).astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-12)
        vecs.append(v)
    return np.stack(vecs, axis=0)

def test_crud_and_search_pipeline():
    assert DB_FILE.exists(), "Run: python scripts/init_db.py"
    store = LTMStore(db_path=DB_FILE)

    # insert
    m1 = store.insert_memory(user_id="u1", kind="preference", text="Kahvemi sütlü severim.", embedding=fake_embed(["Kahvemi sütlü"])[0])
    m2 = store.insert_memory(user_id="u1", kind="fact",        text="Takım: Beşiktaş", embedding=fake_embed(["Beşiktaş"])[0])
    m3 = store.insert_memory(user_id="u1", kind="note",        text="Ofis Maslak'ta.", embedding=fake_embed(["Ofis Maslak"])[0])

    # get
    got = store.get_memory(m1)
    assert got and got.text.startswith("Kahvemi")

    # update
    store.update_memory_text(m2, "Takım: Galatasaray", fake_embed(["Galatasaray"])[0])
    got2 = store.get_memory(m2)
    assert "Galatasaray" in got2.text

    # search (FTS + cosine)
    hits = store.search(user_id="u1", query_text="kahve süt", embed_fn=fake_embed, topk=2)
    assert len(hits) >= 1
    assert "Kahvemi sütlü" in hits[0]["text"]

    # helper
    ctx = retrieve_context(store, "u1", "kahve", fake_embed, topk=2)
    assert any("Kahvemi" in line for line in ctx)

    # delete
    store.delete_memory(m3)
    assert store.get_memory(m3) is None
