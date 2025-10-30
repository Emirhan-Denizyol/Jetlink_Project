from __future__ import annotations
import re
from typing import Optional, Tuple

FORGET_RE = re.compile(r"^\s*#forget\s+(\d+)\s*$", re.IGNORECASE)
UPDATE_RE = re.compile(r"^\s*#update\s+(\d+):\s*(.+)$", re.IGNORECASE)

def parse_forget_cmd(text: str) -> Optional[int]:
    m = FORGET_RE.match(text)
    return int(m.group(1)) if m else None

def parse_update_cmd(text: str) -> Optional[Tuple[int, str]]:
    m = UPDATE_RE.match(text)
    if not m:
        return None
    mem_id = int(m.group(1))
    new_text = m.group(2).strip()
    return mem_id, new_text

def should_suggest_save(user_text: str) -> bool:
    """
    Basit bir sezgi: 12+ kelime ve 'hatırla', 'seviyorum', 'tercih', 'adres', 'doğum' vb. sinyaller
    """
    t = user_text.lower()
    longish = len(t.split()) >= 12
    cues = any(k in t for k in ["hatırla", "seviyorum", "tercih", "adres", "doğum", "telefon", "mail"])
    return longish or cues
