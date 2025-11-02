# --- path fix ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- env yükle ---
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from pathlib import Path
import subprocess, sys as _sys
import re
import json
import time
import unicodedata

# Config ve yardımcı modüller
from src.config import STM_TOKEN_BUDGET, STM_MAX_MESSAGES
from src.embed.google_embed import embed_texts_google as embed_fn
from src.llm.gemini_client import chat_complete
from src.memory.retrieval import retrieve_context  # conv_id destekli olmalı
from src.memory.ltm_store import LTMStore
from src.memory.stm import STM
from src.chat.store import ChatStore

from src.web.search import web_search, enrich_results_with_snippets, format_web_context

DB_PATH = Path("data/memory.db")
USER_ID = "demo-user"  # gerçekte auth sonrası dolar

# --- DB kontrol & otomatik oluşturma ---
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if not DB_PATH.exists():
    try:
        subprocess.run([_sys.executable, "scripts/init_db.py"], check=True)
        st.success("Veritabanı otomatik olarak oluşturuldu ✅")
    except Exception as e:
        st.error(f"DB init hatası: {e}")
        st.stop()

# --- UI ayarları ---
st.set_page_config(page_title="Hafıza Aracı Geliştirme", page_icon="🧠", layout="wide")

# --- Bellek yöneticileri ---
ltm = LTMStore(db_path=DB_PATH)
chat = ChatStore(db_path=DB_PATH)

# --- Yardımcı: Yeni/Değişen sohbet için UI state reset ---
def _reset_session_for_new_or_changed_conv(new_conv_id: int):
    """Yeni sohbet başlatıldığında veya sohbet değiştirildiğinde UI durumunu sıfırlar."""
    st.session_state.current_conv = new_conv_id
    # STM'i taze kur (eski konuşmanın tamponu taşınmasın)
    st.session_state.stm = STM(
        token_budget=STM_TOKEN_BUDGET,
        max_messages=(STM_MAX_MESSAGES or None)
    )
    # Geçici bayraklar/cache
    st.session_state.quote_text = None
    st.session_state["_last_loaded_conv"] = None  # bir sonraki render'da bu conv için STM yüklenir

# --- Session state ---
if "current_conv" not in st.session_state:
    convs = chat.list_conversations(USER_ID)
    st.session_state.current_conv = convs[0]["id"] if convs else chat.create_conversation(USER_ID, "Yeni Sohbet")

if "quote_text" not in st.session_state:
    st.session_state.quote_text = None

if "stm" not in st.session_state:
    st.session_state.stm = STM(
        token_budget=STM_TOKEN_BUDGET,
        max_messages=(STM_MAX_MESSAGES or None)
    )

# ================================
# Sidebar: Sohbet listesi
# ================================
with st.sidebar:
    st.header("Sohbetler")
    convs = chat.list_conversations(USER_ID)
    for c in convs:
        if st.button(c["title"], key=f"conv_{c['id']}", use_container_width=True):
            if st.session_state.get("current_conv") != c["id"]:
                _reset_session_for_new_or_changed_conv(c["id"])
                st.rerun()

    st.divider()

    new_title = st.text_input("Yeni sohbet adı", value="Yeni Sohbet")
    if st.button("➕ Oluştur", use_container_width=True):
        cid = chat.create_conversation(USER_ID, new_title or "Yeni Sohbet")
        _reset_session_for_new_or_changed_conv(cid)
        st.rerun()

    rename = st.text_input("Yeniden adlandır", value="", placeholder="Yeni başlık…")
    if st.button("Yeniden Adlandır", use_container_width=True):
        if rename.strip():
            chat.rename_conversation(st.session_state.current_conv, rename.strip())
            st.rerun()

    if st.button("🗑️ Sil", use_container_width=True):
        chat.delete_conversation(st.session_state.current_conv)
        left = chat.list_conversations(USER_ID)
        next_id = left[0]["id"] if left else chat.create_conversation(USER_ID, "Yeni Sohbet")
        _reset_session_for_new_or_changed_conv(next_id)
        st.rerun()

# ================================
# Ana panel
# ================================
conv_id = st.session_state.current_conv
st.title("🧠 Chat Memory Bot")

# STM'yi DB'deki mesajlardan yükle (yalnızca sohbet değiştiğinde)
if st.session_state.get("_last_loaded_conv") != conv_id:
    msgs = chat.get_messages(conv_id)
    st.session_state.stm = STM(
        token_budget=STM_TOKEN_BUDGET,
        max_messages=(STM_MAX_MESSAGES or None)
    )
    st.session_state.stm.load(msgs)
    st.session_state["_last_loaded_conv"] = conv_id
else:
    msgs = chat.get_messages(conv_id)

# Mesajları göster + "Seç & Sor" butonu
for i, m in enumerate(msgs):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        cols = st.columns([1, 9])
        with cols[0]:
            if st.button("Seç & Sor", key=f"quote_{i}"):
                st.session_state.quote_text = m["content"]
                st.rerun()

# --- Dosya yükleme (çok formatlı giriş) ---
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

st.subheader("📎 Dosya veya Görsel Ekle (isteğe bağlı)")
uploaded_files = st.file_uploader(
    "PDF, TXT, DOCX, PNG, JPG dosyaları yükleyebilirsiniz",
    accept_multiple_files=True,
    type=["pdf", "txt", "docx", "png", "jpg", "jpeg"]
)

uploaded_paths = []
if uploaded_files:
    for uf in uploaded_files:
        file_path = UPLOAD_DIR / uf.name
        with open(file_path, "wb") as f:
            f.write(uf.getbuffer())
        uploaded_paths.append(file_path)

# ================================
# Otomatik profil/hitap kaydı (heuristic)
# ================================
def _maybe_save_profile_prefs(ltm, user_id: str, conv_id: int, text: str):
    """
    Kullanıcı adını ve tercih ettiği hitabı basit kurallarla yakalayıp LTM'e kaydeder.
    """
    t = (text or "").strip()
    if not t:
        return

    # adı yakala: "benim adım X", "adım X"
    m = re.search(r"(?:benim\s+ad[ıi]m|ad[ıi]m)\s+([A-ZÇĞİÖŞÜ][A-Za-zÇĞİÖŞÜçğıöşü\s\-']{2,})", t, flags=re.IGNORECASE)
    name = m.group(1).strip() if m else None

    # hitap yakala: "bana X diye hitap edebilirsin"
    m2 = re.search(r"bana\s+(.+?)\s+diye\s+hitap\s+edebilirsin", t, flags=re.IGNORECASE)
    honorific = m2.group(1).strip() if m2 else None

    if not name and not honorific:
        return  # kaydedecek veri yok

    parts = []
    if name:
        parts.append(f"Kullanıcının adı: {name}")
    if honorific:
        parts.append(f"Tercih edilen hitap: {honorific}")
    mem_text = " ; ".join(parts)

    emb = embed_fn([mem_text])[0]
    ltm.insert_memory(
        user_id=user_id,
        kind="profile",
        text=mem_text,
        embedding=emb,
        source="chat",
        tags=f"conv:{conv_id}",
        expires_at=None
    )

# ================================
# Esnek “konu hatırlatma” yardımcıları (heuristik)
# ================================
_TR_STOPWORDS = {
    "ben","biz","sen","siz","o","ve","veya","ile","için","ama","fakat","de","da","ki","mi","mu","mı","mü",
    "ile","gibi","hakkında","üzerine","önce","daha","önceden","geçen","defa","sohbette","sohbet","konu","konuşma",
    "ne","neyi","neleri","hangi","nasıl","nerede","neleri","şey","bir","iki","çok","az","daha","mi","mı","mu","mü",
    "hakkinda","bahsettik","bahsetmiştik","bahsettiğimiz","konuştuk"
}

def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFKD", s)
    return s

def _extract_topic_keywords(q: str, max_k: int = 4) -> list[str]:
    """Sorudan olası konu anahtar kelimelerini çıkar."""
    import re as _re
    t = _normalize(q)
    toks = _re.findall(r"[a-zçğıöşü0-9\-\.]+", t, flags=_re.IGNORECASE)
    toks = [tok for tok in toks if len(tok) >= 3 and tok not in _TR_STOPWORDS]
    out = []
    for tok in toks:
        if tok not in out:
            out.append(tok)
        if len(out) >= max_k:
            break
    return out

def _is_topic_recap_query(q: str) -> bool:
    """Sabit kalıba bağlı kalmadan, geçmişe referanslı ‘ne konuştuk/bahsettik’ niyetini yakalar."""
    t = _normalize(q)
    verbs = ["konuş", "konustuk", "konuştuk", "bahset", "değin", "hatırla", "gözden", "üzerinden", "değindik"]
    past = ["önce", "daha önce", "geçen", "önceden", "evvel", "önceki", "geçmişte"]
    interrog = ["?", "ne", "hangi", "hatırlıyor", "hatırlar", "hatırladın", "hatırladık", "neydi"]
    v_hit = any(v in t for v in verbs)
    p_hit = any(p in t for p in past)
    i_hit = any(i in t for i in interrog)
    return (v_hit and (p_hit or i_hit)) or ("ne konuştuk" in t)

def _pick_topic_notes(memory_lines: list[str], topic_keywords: list[str], topn: int = 3) -> list[str]:
    """
    retrieve_context çıktısından `note` kayıtlarını ve konu eşleşmesi yüksek olanları seç.
    Satır formatı: "- (scope/kind, yyyy-mm-dd HH:MM:SS) text"
    """
    import re as _re
    scored = []
    for line in memory_lines or []:
        l = _normalize(line)
        m = _re.search(r"- \(\s*(?:[a-z]+)\/([a-z]+)\s*,", l)
        kind = m.group(1) if m else ""
        text_m = _re.search(r"\)\s+(.*)$", line.strip())
        text = text_m.group(1).strip() if text_m else line
        base = 1.0 if "note" in kind else 0.0
        kw_score = sum(1.0 for kw in topic_keywords if kw in l)
        score = base + kw_score
        if base > 0 or kw_score > 0:
            scored.append((score, text))
    if not scored and memory_lines:
        fallback = []
        for line in memory_lines[:topn]:
            text = line.split(") ", 1)[-1] if ") " in line else line
            fallback.append(text.strip())
        return fallback
    scored.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in scored[:topn]]

def _compose_recap_answer(topic_notes: list[str]) -> str:
    """Seçilen notlardan kısa bir özet yanıt üretir."""
    if not topic_notes:
        return ""
    if len(topic_notes) == 1:
        return f"Kısaca şunu ele almıştık: {topic_notes[0]}"
    bullets = "\n".join(f"- {t}" for t in topic_notes)
    return f"Önceki konuşmalarımızdan hatırladıklarım:\n{bullets}"

# ================================
# Hafif çıkarım (flash) yardımcıları
# ================================
if "_last_extract_ts" not in st.session_state:
    st.session_state._last_extract_ts = 0.0

def chat_complete_light(system: str, messages: list[dict]) -> str:
    """
    Extraction ve küçük sınıflandırmalar için düşük maliyetli çağrı.
    .env'deki GEMINI_MODEL'i kullanır; gerekirse fallback uygular.
    """
    import google.generativeai as genai
    import os
    from google.api_core.exceptions import NotFound, ResourceExhausted, GoogleAPICallError

    model_env = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            genai.configure(api_key=api_key)
        except Exception:
            pass  # zaten configure edilmiş olabilir

    content = [{"role": "user", "parts": [f"[SYSTEM]\n{system.strip()}"]}]
    for m in messages:
        content.append({"role": m.get("role", "user"), "parts": [m.get("content", "")]})

    candidates = [model_env]
    if "2.0" in model_env:
        candidates += ["gemini-2.0-pro", "gemini-1.5-pro"]
    else:
        candidates += ["gemini-1.5-flash-001", "gemini-1.5-pro-001", "gemini-1.5-pro"]

    for name in candidates:
        try:
            model = genai.GenerativeModel(name)
            resp = model.generate_content(content)
            if getattr(resp, "text", None):
                return resp.text
            cand = getattr(resp, "candidates", None)
            if cand and getattr(cand[0], "content", None) and getattr(cand[0].content, "parts", None):
                return "".join(getattr(p, "text", "") for p in cand[0].content.parts if hasattr(p, "text"))
            return str(resp)
        except (NotFound, ResourceExhausted, GoogleAPICallError):
            continue
        except Exception:
            continue
    return ""

def _llm_extract_general(user_text: str, assistant_text: str) -> list[dict]:
    """
    Genel ve hafif LLM çıkarımı: flash model + kısa prompt (+ küçük rate guard).
    Her tür bilgiyi (profile/preference/fact/note) yakalamayı hedefler.
    """
    from google.api_core.exceptions import ResourceExhausted

    # Basit rate guard: iki çıkarım arasında min 0.8s
    now = time.monotonic()
    if now - st.session_state._last_extract_ts < 0.8:
        time.sleep(0.8 - (now - st.session_state._last_extract_ts))
    st.session_state._last_extract_ts = time.monotonic()

    system = (
        "You extract long-term useful memories from a single turn of dialog.\n"
        "- Return ONLY a valid JSON array with items: {kind, text, ttl_days}.\n"
        "- kind ∈ {profile, preference, fact, note}.\n"
        "- text must be short, atomic, future-useful; avoid ephemeral numbers/links.\n"
        "- ttl_days may be null; use a small int for time-bound notes.\n"
        "Output strictly the JSON array. No prose."
    )

    prompt = (
        f"USER: {user_text}\n"
        f"ASSISTANT: {assistant_text}\n"
        "Extract JSON now:"
    )

    # 1) LLM ile dene
    try:
        raw = chat_complete_light(system, [{"role": "user", "content": prompt}])
    except ResourceExhausted:
        time.sleep(1.0)
        raw = chat_complete_light(system, [{"role": "user", "content": prompt}])

    # JSON parse
    def _parse(raw_text: str) -> list:
        if not isinstance(raw_text, str) or not raw_text.strip():
            return []
        s = raw_text.strip()
        fence = re.search(r"```(?:json)?\s*(.*?)```", s, flags=re.IGNORECASE | re.DOTALL)
        if fence:
            s = fence.group(1).strip()
        try:
            data = json.loads(s)
            return data if isinstance(data, list) else []
        except Exception:
            pass
        m = re.search(r"\[\s*[\s\S]*\]", s)
        if m:
            try:
                data = json.loads(m.group(0))
                return data if isinstance(data, list) else []
            except Exception:
                pass
        return []

    items = _parse(raw)

    # Şema filtresi
    out = []
    allowed = {"profile", "preference", "fact", "note"}
    for it in items if isinstance(items, list) else []:
        try:
            k = (it.get("kind") or "").strip().lower()
            txt = (it.get("text") or "").strip()
            ttl = it.get("ttl_days")
            if k in allowed and txt:
                try:
                    ttl = int(ttl) if ttl is not None else None
                except Exception:
                    ttl = None
                out.append({"kind": k, "text": txt, "ttl_days": ttl})
        except Exception:
            continue

    # LLM boş ya da uygunsuz döndüyse → kuralsal fallback
    if not out:
        t_all = f"{(user_text or '')} {(assistant_text or '')}".lower()
        heur = []

        # pozitif tercih: "... seviyorum / severim / tercih ederim"
        for g in re.findall(r"(?:ben\s+)?(.+?)\s+(?:seviyorum|severim|tercih ederim)", t_all):
            g = g.strip()
            if g and len(g) > 2:
                heur.append({"kind": "preference", "text": f"{g} tercih eder.", "ttl_days": None})

        # negatif tercih: "... sevmem / sevmiyorum / tercih etmem"
        for g in re.findall(r"(?:ben\s+)?(.+?)\s+(?:sevmem|sevmiyorum|tercih etmem)", t_all):
            g = g.strip()
            if g and len(g) > 2:
                heur.append({"kind": "preference", "text": f"{g} sevmez.", "ttl_days": None})

        # ad & hitap
        m1 = re.search(r"(?:benim\s+ad[ıi]m|ad[ıi]m)\s+([A-ZÇĞİÖŞÜ][^.,\n]{1,60})", user_text or "", flags=re.IGNORECASE)
        if m1:
            heur.append({"kind": "profile", "text": f"Kullanıcının adı: {m1.group(1).strip()}", "ttl_days": None})
        m2 = re.search(r"bana\s+(.+?)\s+diye\s+hitap\s+edebilirsin", user_text or "", flags=re.IGNORECASE)
        if m2:
            heur.append({"kind": "profile", "text": f"Tercih edilen hitap: {m2.group(1).strip()}", "ttl_days": None})

        out = heur[:3]  # en fazla 3 kayıt

    return out

# --- (A) LLM tabanlı genel bilgi çıkarımı ---
def _auto_extract_memories(user_text: str, assistant_text: str) -> list[dict]:
    """Diyalogdan uzun vadeli yararlı olabilecek memory kayıtlarını çıkarır."""
    return _llm_extract_general(user_text, assistant_text)

# --- (B) Çıkan kayıtları LTM’e güvenli yazma (dup engelleme) ---
def _persist_memories(ltm: LTMStore, user_id: str, conv_id: int, items: list[dict]):
    """
    Çıkarılan kayıtları LTM'e upsert eder.
    - Benzerlik eşiğiyle dup engelleme
    - conv:<id> etiketi ekleme
    """
    wrote = 0
    for it in items:
        kind = it["kind"]
        text = it["text"]
        emb = embed_fn([text])[0]
        try:
            # note için biraz daha esnek eşik
            sim_thresh = 0.80 if kind == "note" else 0.84
            ltm.upsert_if_novel(
                user_id=user_id,
                kind=kind,
                text=text,
                embedding=emb,
                source="chat:auto",
                tags=f"conv:{conv_id}",
                expires_at=None,
                similarity_threshold=sim_thresh,
                recent_limit=200,
                merge_if_similar=False,
            )
            wrote += 1
        except Exception:
            try:
                ltm.insert_memory(
                    user_id=user_id,
                    kind=kind,
                    text=text,
                    embedding=emb,
                    source="chat:auto",
                    tags=f"conv:{conv_id}",
                    expires_at=None,
                )
                wrote += 1
            except Exception:
                pass
    if wrote:
        st.toast(f"💾 {wrote} kayıt kaydedildi.", icon="💾")

# ================================
# LLM tabanlı esnek “konu hatırlatma” (NIYET + ÖZET)
# ================================
def _llm_detect_recap_intent(query: str) -> bool:
    """
    Kullanıcı mesajında 'geçmişte ne konuştuk/bahsettik' niyeti olup olmadığını
    LLM ile tespit eder. YALNIZCA 'YES' veya 'NO' döndürür.
    """
    system = (
        "You are a classifier. Decide if the user's message asks to RECAP past topics "
        "(what we discussed before, what we talked about earlier, remind me what we said, etc.). "
        "Return ONLY 'YES' or 'NO'. No explanations."
    )
    prompt = f"USER MESSAGE:\n{query}\n\nAnswer with YES or NO:"
    ans = chat_complete_light(system, [{"role": "user", "content": prompt}]) or ""
    ans = (ans or "").strip().upper()
    return "YES" in ans and "NO" not in ans

def _llm_compose_recap(memory_lines: list[str], user_query: str, max_items: int = 5) -> str:
    """
    LTM’den gelen memory_lines içinden, kullanıcı sorusuyla en alakalı 3–5 notu seçip
    kısa ve net bir özet yanıt üretmesini LLM’den ister.
    LLM başarısız olursa boş string döner (heuristiğe düşülür).
    """
    listed = "\n".join(f"{i+1}. {line}" for i, line in enumerate(memory_lines[:50]))
    system = (
        "You are a summarizer. Given a list of past conversation memories and the user's question, "
        "select the MOST relevant 3-5 items and compose a concise Turkish recap. "
        "Rules:\n"
        "- Be brief (<= 600 chars).\n"
        "- Use bullet points if multiple items.\n"
        "- Do NOT invent facts not present.\n"
        "- If nothing is relevant, return an empty string."
    )
    prompt = (
        f"KULLANICI SORUSU:\n{user_query}\n\n"
        f"GEÇMİŞ NOTLAR (liste):\n{listed}\n\n"
        f"Lütfen sadece ilgili olanları kullanarak Türkçe kısa bir özet yaz."
    )
    out = chat_complete_light(system, [{"role": "user", "content": prompt}]) or ""
    out = (out or "").strip()
    if not out or out.lower() in {"", "boş", "empty", "none"}:
        return ""
    if len(out) > 800:
        out = out[:780].rstrip() + "…"
    return out

# ================================
# Ana handler
# ================================
def handle_prompt(prompt_text: str, files=None):
    """DB'ye yaz, STM'e ekle, LTM çek, gerekirse web araması yap, Gemini çağır."""
    conv_id_local = st.session_state.current_conv

    # 1) Kullanıcı mesajını kaydet + STM
    chat.add_message(conv_id_local, "user", prompt_text)
    st.session_state.stm.push("user", prompt_text)

    # Basit isim/hitap heuristiği
    _maybe_save_profile_prefs(ltm, USER_ID, conv_id_local, prompt_text)

    # 2) LTM retrieval (yerel + küresel hibrit)
    memory_lines = retrieve_context(
        ltm, USER_ID, prompt_text, embed_fn,
        topk=10,
        conv_id=st.session_state.current_conv
    )
    mem_block = "\n".join(memory_lines)

    # 🔎 2.5) LLM tabanlı “konu hatırlatma” kısa devresi (öncelikli)
    try:
        if _llm_detect_recap_intent(prompt_text):
            llm_recap = _llm_compose_recap(memory_lines, prompt_text, max_items=5)
            if llm_recap.strip():
                reply = llm_recap
                # Kaydet + STM
                chat.add_message(conv_id_local, "assistant", reply)
                st.session_state.stm.push("assistant", reply)
                # Hafıza çıkarımı (konu izi güçlensin)
                extracted = _auto_extract_memories(prompt_text, reply)
                _persist_memories(ltm, USER_ID, conv_id_local, extracted)
                st.rerun()
                return
    except Exception:
        # LLM başarısızsa, hemen alttaki heuristiğe düş
        pass

    # 🔎 2.6) Heuristik “konu hatırlatma” kısa devresi (LLM boş/hatalıysa)
    if _is_topic_recap_query(prompt_text):
        topic_kws = _extract_topic_keywords(prompt_text)
        notes = _pick_topic_notes(memory_lines, topic_kws, topn=3)
        draft = _compose_recap_answer(notes)
        if draft.strip():
            reply = draft
            chat.add_message(conv_id_local, "assistant", reply)
            st.session_state.stm.push("assistant", reply)
            extracted = _auto_extract_memories(prompt_text, reply)
            _persist_memories(ltm, USER_ID, conv_id_local, extracted)
            st.rerun()
            return

    # 3) İlk Gemini çağrısı — gerekirse web araması isteyecek
    system = f"""
    You are a helpful assistant.
    You have access to MEMORY CONTEXT (user-specific info).
    If the user's question requires current or real-time information 
    (like recent events, prices, weather, or today's facts),
    respond ONLY with: "SEARCH_NEEDED: <search query>".
    Otherwise, answer normally using your knowledge and MEMORY CONTEXT.

    When MEMORY CONTEXT contains multiple relevant user memories (e.g., positive and negative preferences), synthesize **all** of them explicitly in the answer.

    MEMORY CONTEXT:
    {mem_block}
    """
    reply = chat_complete(system, st.session_state.stm.as_list(), files=files)

    # 4) Eğer SEARCH_NEEDED döndüyse → DuckDuckGo araması yap (zenginleştir)
    if isinstance(reply, str) and reply.startswith("SEARCH_NEEDED:"):
        query = reply.replace("SEARCH_NEEDED:", "").strip()
        with st.spinner(f"🔎 Web araması yapılıyor: {query}"):
            results_raw = web_search(query, max_results=6)
            results = enrich_results_with_snippets(results_raw)
            web_block = format_web_context(results, max_items=3)

        followup_system = f"""
        The user asked: "{prompt_text}"
        You requested a web search for: {query}
        Here are the web results (summarized):
        {web_block}

        Guidelines:
        - Prefer information corroborated by multiple sources.
        - If sources disagree, state the uncertainty briefly.
        - Cite or mention sources concisely in prose when useful.
        - Be concise and factual.
        """
        reply = chat_complete(followup_system, st.session_state.stm.as_list(), files=files)

    # 5) Genel bilgi çıkarımı + LTM'e güvenli yazım
    extracted = _auto_extract_memories(prompt_text, reply)
    _persist_memories(ltm, USER_ID, conv_id_local, extracted)

    # 6) Cevabı kaydet + STM
    chat.add_message(conv_id_local, "assistant", reply)
    st.session_state.stm.push("assistant", reply)

    st.rerun()

# ================================
# Girdi akışı
# ================================
if st.session_state.quote_text:
    st.info("Seçtiğiniz metni alıntılayarak soru sorabilirsiniz.")
    default_quote = f"> {st.session_state.quote_text}\n\nSorunuz: "
    with st.form("quote_form", clear_on_submit=True):
        ask = st.text_area("Alıntı ile sor:", value=default_quote, height=160)
        c1, c2 = st.columns([1, 1])
        with c1:
            send = st.form_submit_button("Gönder")
        with c2:
            cancel = st.form_submit_button("İptal")
    if cancel:
        st.session_state.quote_text = None
        st.rerun()
    if send and ask.strip():
        st.session_state.quote_text = None
        handle_prompt(ask.strip(), files=uploaded_paths)
else:
    prompt = st.chat_input("Bir şey yazın…")
    if prompt:
        handle_prompt(prompt, files=uploaded_paths)
