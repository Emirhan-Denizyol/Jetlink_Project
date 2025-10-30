from __future__ import annotations
import re
from typing import List

_WS = re.compile(r"\s+")

def normalize(text: str) -> str:
    text = text.strip()
    text = _WS.sub(" ", text)
    return text

def approx_token_count(text: str) -> int:
    # 4 char ~ 1 token kabulu
    return max(1, len(text) // 4)

def chunk_by_chars(text: str, max_chars: int = 800) -> List[str]:
    text = normalize(text)
    if len(text) <= max_chars:
        return [text]
    out, cur = [], []
    size = 0
    for w in text.split(" "):
        if size + len(w) + 1 > max_chars:
            out.append(" ".join(cur))
            cur, size = [w], len(w)
        else:
            cur.append(w)
            size += len(w) + 1
    if cur:
        out.append(" ".join(cur))
    return out
