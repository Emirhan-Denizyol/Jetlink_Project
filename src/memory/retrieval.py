# src/memory/retrieval.py
from __future__ import annotations
from typing import List
from src.memory.ltm_store import LTMStore

def retrieve_context(
    store: LTMStore,
    user_id: str,
    query_text: str,
    embed_fn,
    topk: int = 5
) -> List[str]:
    hits = store.search(user_id=user_id, query_text=query_text, embed_fn=embed_fn, topk=topk)
    return [f"- ({h['kind']}, {h['created_at']}) {h['text']}" for h in hits]
