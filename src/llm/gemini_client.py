"""from __future__ import annotations
from typing import List, Dict
import google.generativeai as genai
from src.config import GOOGLE_API_KEY, GEMINI_MODEL

def chat_complete(system_prompt: str, messages: List[Dict[str, str]]) -> str:
    if not GOOGLE_API_KEY:
        # API yoksa sade bir eko cevabı dön (demo/fallback)
        user_last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"(LLM yok: Basit yanıt) {user_last}"
    genai.configure(api_key=GOOGLE_API_KEY)
    content = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
    prompt = f"{system_prompt}\n\n{content}"
    resp = genai.GenerativeModel(GEMINI_MODEL).generate_content(prompt)
    return (resp.text or "").strip()
"""

from __future__ import annotations
from typing import List, Dict, Optional, Union
import google.generativeai as genai
from src.config import GOOGLE_API_KEY, GEMINI_MODEL
from pathlib import Path
import mimetypes

def chat_complete(
    system_prompt: str,
    messages: List[Dict[str, str]],
    files: Optional[List[Union[str, Path]]] = None
) -> str:
    """
    Gemini modeline çok formatlı (metin + dosya) içerik gönderir.
    - files: PDF, TXT, DOCX, PNG, JPG, vb. desteklenir.
    """
    if not GOOGLE_API_KEY:
        user_last = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        return f"(LLM yok: Basit yanıt) {user_last}"

    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # 💬 Mesajları tek stringe birleştir
    text_block = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
    content = [system_prompt, text_block]

    # 📎 Dosyaları yükle (isteğe bağlı)
    uploaded_files = []
    if files:
        for f in files:
            f = Path(f)
            if not f.exists():
                continue
            mime, _ = mimetypes.guess_type(str(f))
            upload = genai.upload_file(path=str(f), mime_type=mime or "application/octet-stream")
            uploaded_files.append(upload)
        content.extend(uploaded_files)

    # 🚀 Modeli çalıştır
    resp = model.generate_content(content)
    return (resp.text or "").strip()
