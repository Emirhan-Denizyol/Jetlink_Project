from __future__ import annotations
from typing import List, Dict

def rough_token_count(text: str) -> int:
    # Yaklaşık token: 4 karakter ~ 1 token varsayımı
    return max(1, len(text) // 4)

class STM:
    """
    Konuşma içi bağlamı yönetir.
    - max_messages: sadece son N mesajı tutar (N varsa)
    - token_budget: ek güvenlik. Çok büyük ver (örn. 10_000_000) => fiilen devre dışı
    """
    def __init__(self, token_budget: int = 1500, max_messages: int | None = None):
        self.token_budget = token_budget
        self.max_messages = max_messages
        self.messages: List[Dict[str, str]] = []

    def load(self, rows: List[Dict[str, str]]) -> None:
        self.messages = list(rows)
        self._trim()

    def push(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        self._trim()

    def as_list(self) -> List[Dict[str, str]]:
        return list(self.messages)

    def reset(self) -> None:
        """Oturum değişimlerinde kullanışlı: tamponu tamamen temizler."""
        self.messages = []

    def _trim(self):
        # 1) Mesaj sayısı limiti (varsa): system mesajlarını mümkün olduğunca koru
        if self.max_messages is not None and len(self.messages) > self.max_messages:
            i = 0
            while len(self.messages) > self.max_messages and i < len(self.messages):
                if self.messages[i].get("role") != "system":
                    del self.messages[i]
                else:
                    i += 1
            while len(self.messages) > self.max_messages:
                del self.messages[0]

        # 2) Token bütçesi limiti
        def cost(msg): return rough_token_count(msg.get("content", "")) + 4
        total = sum(cost(m) for m in self.messages)
        if total <= self.token_budget:
            return
        i = 0
        while total > self.token_budget and i < len(self.messages):
            if self.messages[i].get("role") != "system":
                total -= cost(self.messages[i])
                del self.messages[i]
            else:
                i += 1
        while total > self.token_budget and len(self.messages) > 1:
            total -= cost(self.messages[0])
            del self.messages[0]
