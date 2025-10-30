import numpy as np
from pathlib import Path
from src.memory.ltm_store import LTMStore
from src.memory.retrieval import retrieve_context

DB_FILE = Path("data/memory.db")

def fake_embed(texts):
    vecs = []
    for t in texts:
        rng = np.random.default_rng(abs(hash(t)) % (2**32))
        v = rng.normal(size=64).astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-12)
        vecs.append(v)
    return np.stack(vecs, axis=0)

def test_retrieve_basic_flow():
    assert DB_FILE.exists(), "Run: python scripts/init_db.py"
    store = LTMStore(db_path=DB_FILE)

    # tohum veriler
    m1 = store.insert_memory("u1", "preference", "Çayı şekersiz içerim.", fake_embed(["çay şekersiz"])[0])
    m2 = store.insert_memory("u1", "note", "Ofis Mecidiyeköy'de.", fake_embed(["ofis mecidiyeköy"])[0])

    ctx = retrieve_context(store, "u1", "çay", fake_embed, topk=3)
    assert any("Çayı şekersiz" in line for line in ctx)

    # temizle
    store.delete_memory(m1)
    store.delete_memory(m2)
