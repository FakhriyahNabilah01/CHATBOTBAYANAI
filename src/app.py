# src/app.py
# Jalankan: streamlit run src/app.py

import os
import sys
import io
import uuid
from contextlib import redirect_stdout, redirect_stderr
from typing import Tuple

import streamlit as st

# Pastikan import modul di folder src bisa jalan
SRC_DIR = os.path.dirname(__file__)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# Import controller utama kamu
from controller import controller  # pastikan file: src/controller.py


# ----------------------------
# Helpers
# ----------------------------
def _capture_controller_output(user_text: str, session_id: str) -> Tuple[str, str]:
    """
    Jalankan controller() sambil menangkap semua print/sys.stdout.
    Return: (content_text, debug_text)
    """
    buf_out = io.StringIO()
    buf_err = io.StringIO()

    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            ret = controller(user_text, session_id=session_id)
    except Exception as e:
        # Kalau controller meledak, tampilkan errornya
        return f"❌ Terjadi error saat memproses:\n\n```text\n{e}\n```", ""

    raw = (buf_out.getvalue() or "").strip()
    err = (buf_err.getvalue() or "").strip()
    ret_text = (ret or "").strip()

    # Kalau controller tidak ngeprint apa-apa, pakai return value
    if not raw and ret_text:
        raw = ret_text
    # Kalau ada print + return dan return-nya bukan bagian dari print, tempel di bawah
    elif raw and ret_text and (ret_text not in raw):
        raw = raw + "\n\n" + ret_text

    if err:
        raw = raw + "\n\n```text\n" + err + "\n```"

    content, debug = _split_debug(raw)
    content = _beautify_output(content)

    return content, debug


def _split_debug(text: str) -> Tuple[str, str]:
    """
    Pisahkan baris debug yang diawali '[' (misal [DEBUG], [✅ MANUAL], [DEDUP ...])
    dari konten utama.
    """
    debug_lines = []
    content_lines = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped[:30]:
            debug_lines.append(line)
        else:
            content_lines.append(line)

    content = "\n".join(content_lines).strip()
    debug = "\n".join(debug_lines).strip()
    return content, debug


def _beautify_output(text: str) -> str:
    """
    Sedikit rapihin output supaya enak dibaca di UI chat.
    - Ganti garis "════" jadi pemisah markdown.
    - Rapihin judul ayat jadi gaya "📖 Surat ... ayat ..."
    """
    if not text:
        return text

    # Ganti garis pemisah yang panjang jadi markdown HR
    # (biar tampilan Streamlit lebih clean)
    text = text.replace("═" * 60, "---")

    # Ubah format "**Ayat X – Surat**" jadi "📖 **Surat {Surat} ayat {X}**"
    # Contoh: **Ayat 9 – Al-'Adiyat** -> 📖 **Surat Al-'Adiyat ayat 9**
    import re
    text = re.sub(
        r"\*\*Ayat\s+(\d+)\s+–\s+(.+?)\*\*",
        r"📖 **Surat \2 ayat \1**",
        text
    )

    # Tambah emoji kecil biar variatif tapi tetap simple
    text = text.replace("**Artinya:**", "📝 **Artinya:**")
    text = text.replace("**Kategori:**", "🧩 **Kategori:**")
    text = text.replace("**Tafsir Kemenag (Tahlili):**", "🟩 **Tafsir Kemenag (Tahlili):**")
    text = text.replace("**Tafsir Kemenag (Wajiz):**", "🟦 **Tafsir Kemenag (Wajiz):**")
    text = text.replace("**Tafsir Buya Hamka:**", "🟥 **Tafsir Buya Hamka:**")

    # Kalau ada "Berikut ayat-ayat..." kita biarin, itu header bagus.
    return text


# ----------------------------
# UI
# ----------------------------
st.set_page_config(
    page_title="BayanAI",
    page_icon="📖",
    layout="centered",
)

CUSTOM_CSS = """
<style>
/* Biar konten terasa center & rapi */
.block-container { max-width: 820px; padding-top: 28px; }

/* Rapihin chat bubble spacing */
[data-testid="stChatMessage"] { padding: 6px 0px; }

/* Biar markdown output nyaman dibaca */
.chat-output p, .chat-output li { line-height: 1.6; }

/* Kecilkan jarak HR */
.chat-output hr { margin: 14px 0; }

/* Judul center ala screenshot */
.hero {
  text-align: center;
  margin-bottom: 18px;
}
.hero h1 {
  font-size: 40px;
  margin: 0;
}
.hero p {
  margin-top: 6px;
  color: #6b7280;
  font-size: 14px;
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown(
    """
<div class="hero">
  <h1>📖 Chatbot Hari Kiamat &amp; Juz 30</h1>
  <p>Jawaban berbasis ayat, terjemahan, kategori, dan tafsir dari database Neo4j.</p>
</div>
""",
    unsafe_allow_html=True,
)

# Session init
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of dict {role, content, debug?}

if "show_debug" not in st.session_state:
    st.session_state.show_debug = False

if "preferred_sources" not in st.session_state:
    st.session_state.preferred_sources = ["all"]


# # Sidebar controls
# with st.sidebar:
#     st.header("⚙️ Pengaturan")

#     st.session_state.show_debug = st.toggle("Tampilkan debug", value=st.session_state.show_debug)

#     sources = st.multiselect(
#         "Tafsir yang ditampilkan",
#         options=["all", "tahlili", "wajiz", "hamka"],
#         default=st.session_state.preferred_sources,
#         help="Kalau dipilih, app akan menambahkan kata kunci ini ke prompt supaya filter sumber aktif."
#     )
#     st.session_state.preferred_sources = sources if sources else ["all"]

#     if st.button("🧹 Clear chat", use_container_width=True):
#         st.session_state.messages = []
#         # session_id baru biar state internal controller ikut fresh
#         st.session_state.session_id = str(uuid.uuid4())
#         st.rerun()


# Render message history
for msg in st.session_state.messages:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🕌"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(f"<div class='chat-output'>{msg['content']}</div>", unsafe_allow_html=True)

        if st.session_state.show_debug and msg.get("debug"):
            with st.expander("Lihat debug"):
                st.code(msg["debug"], language="text")


# Chat input (di bawah)
prompt = st.chat_input("Tanyakan sesuatu... (contoh: 'gambaran hisab' atau 'kiamat')")

if prompt:
    # inject sumber tafsir biar detect_sources ke-trigger tanpa ganggu maksud besar prompt
    # (misal user ga nulis 'hamka', tapi di sidebar pilih hamka)
    inject = ""
    if st.session_state.preferred_sources and "all" not in st.session_state.preferred_sources:
        inject = " " + " ".join(st.session_state.preferred_sources)

    final_prompt = (prompt + inject).strip()

    st.session_state.messages.append({"role": "user", "content": final_prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(final_prompt)

    with st.chat_message("assistant", avatar="🕌"):
        with st.spinner("Mencari ayat & menyusun jawaban..."):
            content, debug = _capture_controller_output(final_prompt, st.session_state.session_id)

        st.markdown(f"<div class='chat-output'>{content}</div>", unsafe_allow_html=True)

        if st.session_state.show_debug and debug:
            with st.expander("Lihat debug"):
                st.code(debug, language="text")

    st.session_state.messages.append({"role": "assistant", "content": content, "debug": debug})
