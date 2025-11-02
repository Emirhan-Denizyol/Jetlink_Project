# src/memory/retrieval.py
from __future__ import annotations
from typing import List, Optional
from src.memory.ltm_store import LTMStore

def _norm_text(s: str) -> str:
    """Tekilleştirme için basit normalizasyon."""
    return (" ".join((s or "").split())).strip().lower()

def retrieve_context(
    store: LTMStore,
    user_id: str,
    query_text: str,
    embed_fn,
    topk: int = 5,
    *,
    conv_id: Optional[int] = None,
    topk_local: int = 4,
    topk_global: int = 4,
    w_local: float = 1.0,
    w_global: float = 1.0,
) -> List[str]:
    """
    Yerel (aynı sohbet) + Küresel (tüm sohbetler) hafızayı birlikte sorgular.
    - conv_id verilirse, LTM'de tags/source alanında 'conv:<conv_id>' geçen kayıtlar yerel sayılır.
    - Sonuçlar ağırlıklı skorlarla birleştirilir (store tarafında).
    - Tekilleştirilmiş, kısa, okunabilir satırlar döndürür.
    """
    # 1) Arama (scoped varsa onu, yoksa klasik global)
    if conv_id is None:
        hits = store.search(
            user_id=user_id,
            query_text=query_text,
            embed_fn=embed_fn,
            topk=topk,
        )
    else:
        hits = store.search_scoped(
            user_id=user_id,
            query_text=query_text,
            embed_fn=embed_fn,
            conv_id=conv_id,
            topn_prefilter=150,
            topk_local=topk_local,
            topk_global=topk_global,
            w_local=w_local,
            w_global=w_global,
        )

    # 2) Sonuçları tekilleştir (aynı text bir kez görünsün – scope/kind farkına rağmen)
    deduped = []
    seen_texts = set()
    for h in hits or []:
        key = _norm_text(h.get("text", ""))
        if not key:
            continue
        if key in seen_texts:
            continue
        seen_texts.add(key)
        deduped.append(h)

    # 3) Üst 'topk' uygula (store zaten skorla sıralı döndürüyor)
    if isinstance(topk, int) and topk > 0:
        deduped = deduped[:topk]

    # 4) Eğer hâlâ boşsa: güvenli bir global fallback (özellikle çok kısıtlı conv filtrelerinde işe yarar)
    if not deduped:
        fallback = store.search(
            user_id=user_id,
            query_text=query_text,
            embed_fn=embed_fn,
            topk=topk,
        )
        for h in fallback or []:
            key = _norm_text(h.get("text", ""))
            if key and key not in seen_texts:
                seen_texts.add(key)
                deduped.append(h)
                if len(deduped) >= (topk if isinstance(topk, int) and topk > 0 else 9999):
                    break

    # 5) Sunum formatı (geriye dönük uyumluluk)
    lines: List[str] = []
    for h in deduped:
        scope_tag = f"{h.get('scope')}" if h.get("scope") else "global"
        lines.append(f"- ({scope_tag}/{h['kind']}, {h['created_at']}) {h['text']}")
    return lines
