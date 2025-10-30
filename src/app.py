"""# --- path fix ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from pathlib import Path
import subprocess, sys

# Config ve yardımcı modüller
from src.config import STM_TOKEN_BUDGET, STM_MAX_MESSAGES
from src.embed.google_embed import embed_texts_google as embed_fn
from src.llm.gemini_client import chat_complete
from src.memory.retrieval import retrieve_context
from src.memory.ltm_store import LTMStore
from src.memory.stm import STM
from src.chat.store import ChatStore

DB_PATH = Path("data/memory.db")
USER_ID = "demo-user"  # gerçekte auth sonrası dolar

# --- DB kontrol & otomatik oluşturma ---
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if not DB_PATH.exists():
    try:
        subprocess.run([sys.executable, "scripts/init_db.py"], check=True)
        st.success("Veritabanı otomatik olarak oluşturuldu ✅")
    except Exception as e:
        st.error(f"DB init hatası: {e}")
        st.stop()

# --- UI ayarları ---
st.set_page_config(page_title="Hafıza Aracı Geliştirme", page_icon="🧠", layout="wide")

# --- Bellek yöneticileri ---
ltm = LTMStore(db_path=DB_PATH)
chat = ChatStore(db_path=DB_PATH)

# --- Session state ---
if "current_conv" not in st.session_state:
    convs = chat.list_conversations(USER_ID)
    st.session_state.current_conv = convs[0]["id"] if convs else chat.create_conversation(USER_ID, "Yeni Sohbet")

if "stm" not in st.session_state:
    st.session_state.stm = STM(
        token_budget=STM_TOKEN_BUDGET,
        max_messages=(STM_MAX_MESSAGES or None)
    )

# --- Sidebar: Sohbet listesi ---
with st.sidebar:
    st.header("Sohbetler")
    convs = chat.list_conversations(USER_ID)
    for c in convs:
        if st.button(c["title"], key=f"conv_{c['id']}", use_container_width=True):
            st.session_state.current_conv = c["id"]
    st.divider()
    new_title = st.text_input("Yeni sohbet adı", value="Yeni Sohbet")
    if st.button("➕ Oluştur", use_container_width=True):
        cid = chat.create_conversation(USER_ID, new_title or "Yeni Sohbet")
        st.session_state.current_conv = cid
    rename = st.text_input("Yeniden adlandır", value="", placeholder="Yeni başlık…")
    if st.button("Yeniden Adlandır", use_container_width=True):
        if rename.strip():
            chat.rename_conversation(st.session_state.current_conv, rename.strip())
            st.rerun()
    if st.button("🗑️ Sil", use_container_width=True):
        chat.delete_conversation(st.session_state.current_conv)
        left = chat.list_conversations(USER_ID)
        st.session_state.current_conv = left[0]["id"] if left else chat.create_conversation(USER_ID, "Yeni Sohbet")
        st.rerun()

# --- Ana panel ---
conv_id = st.session_state.current_conv
st.title("🧠 Chat Memory Bot")

# STM'yi DB'deki mesajlardan yükle (sohbet değiştiğinde)
msgs = chat.get_messages(conv_id)
st.session_state.stm.load(msgs)

# Mesajları göster
for m in msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Kullanıcı girişi
prompt = st.chat_input("Bir şey yazın…")
if prompt:
    # 1) Kullanıcı mesajını kaydet ve STM'e ekle
    chat.add_message(conv_id, "user", prompt)
    st.session_state.stm.push("user", prompt)

    # 2) LTM'den bağlamsal hatıraları çek
    memory_lines = retrieve_context(ltm, USER_ID, prompt, embed_fn, topk=5)

    # 3) Gemini modeline gönder
    mem_block = "\n".join(memory_lines)
    system = (
        "You are a helpful assistant. Use MEMORY CONTEXT if relevant.\n\n"
        f"MEMORY CONTEXT:\n{mem_block}\n"
    )
    reply = chat_complete(system, st.session_state.stm.as_list())

    # 4) Cevabı kaydet ve STM'e ekle
    chat.add_message(conv_id, "assistant", reply)
    st.session_state.stm.push("assistant", reply)

    st.rerun()
"""

# --- path fix ---
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from pathlib import Path
import subprocess, sys as _sys

# Config ve yardımcı modüller
from src.config import STM_TOKEN_BUDGET, STM_MAX_MESSAGES
from src.embed.google_embed import embed_texts_google as embed_fn
from src.llm.gemini_client import chat_complete
from src.memory.retrieval import retrieve_context
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

# --- Session state ---
if "current_conv" not in st.session_state:
    convs = chat.list_conversations(USER_ID)
    st.session_state.current_conv = convs[0]["id"] if convs else chat.create_conversation(USER_ID, "Yeni Sohbet")

# Alıntı akışı için state
if "quote_text" not in st.session_state:
    st.session_state.quote_text = None

if "stm" not in st.session_state:
    st.session_state.stm = STM(
        token_budget=STM_TOKEN_BUDGET,
        max_messages=(STM_MAX_MESSAGES or None)
    )

# --- Sidebar: Sohbet listesi ---
with st.sidebar:
    st.header("Sohbetler")
    convs = chat.list_conversations(USER_ID)
    for c in convs:
        if st.button(c["title"], key=f"conv_{c['id']}", use_container_width=True):
            st.session_state.current_conv = c["id"]
    st.divider()
    new_title = st.text_input("Yeni sohbet adı", value="Yeni Sohbet")
    if st.button("➕ Oluştur", use_container_width=True):
        cid = chat.create_conversation(USER_ID, new_title or "Yeni Sohbet")
        st.session_state.current_conv = cid
    rename = st.text_input("Yeniden adlandır", value="", placeholder="Yeni başlık…")
    if st.button("Yeniden Adlandır", use_container_width=True):
        if rename.strip():
            chat.rename_conversation(st.session_state.current_conv, rename.strip())
            st.rerun()
    if st.button("🗑️ Sil", use_container_width=True):
        chat.delete_conversation(st.session_state.current_conv)
        left = chat.list_conversations(USER_ID)
        st.session_state.current_conv = left[0]["id"] if left else chat.create_conversation(USER_ID, "Yeni Sohbet")
        st.rerun()

# --- Ana panel ---
conv_id = st.session_state.current_conv
st.title("🧠 Chat Memory Bot")

# STM'yi DB'deki mesajlardan yükle (sohbet değiştiğinde)
msgs = chat.get_messages(conv_id)
st.session_state.stm.load(msgs)

# Mesajları göster + "Seç & Sor" butonu
for i, m in enumerate(msgs):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        # Her mesajın altına "Seç & Sor" ekle
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

# --- Girdi işlemleri için ortak handler ---
def handle_prompt(prompt_text: str, files=None):
    """DB'ye yaz, STM'e ekle, LTM çek, gerekirse web araması yap, Gemini çağır."""
    # 1️⃣ Kullanıcı mesajını kaydet + STM
    chat.add_message(conv_id, "user", prompt_text)
    st.session_state.stm.push("user", prompt_text)

    # 2️⃣ LTM retrieval
    memory_lines = retrieve_context(ltm, USER_ID, prompt_text, embed_fn, topk=5)
    mem_block = "\n".join(memory_lines)

    # 3️⃣ İlk Gemini çağrısı — gerekirse web araması isteyecek
    system = f"""
    You are a helpful assistant.
    You have access to MEMORY CONTEXT (user-specific info).
    If the user's question requires current or real-time information 
    (like recent events, prices, weather, or today's facts),
    respond ONLY with: "SEARCH_NEEDED: <search query>".
    Otherwise, answer normally using your knowledge and MEMORY CONTEXT.

    MEMORY CONTEXT:
    {mem_block}
    """
    reply = chat_complete(system, st.session_state.stm.as_list(), files=files)

    # 4️⃣ Eğer SEARCH_NEEDED döndüyse → DuckDuckGo araması yap (zenginleştir)
    if isinstance(reply, str) and reply.startswith("SEARCH_NEEDED:"):
        query = reply.replace("SEARCH_NEEDED:", "").strip()
        with st.spinner(f"🔎 Web araması yapılıyor: {query}"):
            results_raw = web_search(query, max_results=6)
            results = enrich_results_with_snippets(results_raw)   # 👈 gövdeyi gerçek sayfa snippet’iyle doldur
            web_block = format_web_context(results, max_items=3)

        # 5️⃣ Web sonuçlarını modele tekrar gönder
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

    # 6️⃣ Cevabı kaydet + STM
    chat.add_message(conv_id, "assistant", reply)
    st.session_state.stm.push("assistant", reply)

    st.rerun()

# --- Alıntı modu (Seç & Sor) ---
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
        # 👇 Alıntı sorularında da dosyaları modele gönder
        handle_prompt(ask.strip(), files=uploaded_paths)

# --- Normal chat input ---
else:
    prompt = st.chat_input("Bir şey yazın…")
    if prompt:
        # 👇 Normal sohbette de dosyaları modele gönder
        handle_prompt(prompt, files=uploaded_paths)
