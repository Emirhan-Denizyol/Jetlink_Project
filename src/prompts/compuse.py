from __future__ import annotations
from typing import List, Dict

def compose_system(memory_lines: List[str]) -> str:
    mem_block = "\n".join(memory_lines) if memory_lines else "(none)"
    return (
        "You are a helpful assistant. Use MEMORY CONTEXT if relevant.\n\n"
        f"MEMORY CONTEXT:\n{mem_block}\n"
    )

def as_messages(stm_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    STM mesajlarını Gemini'ye verilecek biçimde aynen döndürür.
    roles: 'user' / 'assistant' / (opsiyonel) 'system'
    """
    return list(stm_messages)
