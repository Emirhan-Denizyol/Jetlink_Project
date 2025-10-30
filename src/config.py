import os
from dotenv import load_dotenv

# .env dosyasını yükle (.env kök dizindeyse otomatik bulur)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "text-embedding-004")

# Retrieval ayarları
RETRIEVAL_TOPN     = int(os.getenv("RETRIEVAL_TOPN", "100"))
RETRIEVAL_TOPK     = int(os.getenv("RETRIEVAL_TOPK", "5"))
RECENCY_ALPHA      = float(os.getenv("RECENCY_ALPHA", "0.9"))
RECENCY_BETA       = float(os.getenv("RECENCY_BETA", "0.1"))

STM_TOKEN_BUDGET = int(os.getenv("STM_TOKEN_BUDGET", "10000000"))  # pratikte devre dışı
STM_MAX_MESSAGES = int(os.getenv("STM_MAX_MESSAGES", "20"))        # son N mesaj