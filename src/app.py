# src/app.py
# Jalankan lokal: streamlit run src/app.py

import os
import sys
import io
import uuid
from contextlib import redirect_stdout, redirect_stderr
from typing import Tuple

import streamlit as st

# ================================
# PAGE CONFIG (HANYA SEKALI!)
# ================================
st.set_page_config(
    page_title="BayanAI",
    page_icon="📖",
    layout="wide",
)

# ================================
# GATE LOGIN GOOGLE
# ================================
if not st.user.is_logged_in:
    st.title("🔐 Login terlebih dahulu")
    st.write("Silakan login dengan akun Google untuk menggunakan chatbot.")

    if st.button("Login dengan Google"):
        st.login()

    st.stop()

# ================================
# USER SUDAH LOGIN
# ================================
st.sidebar.success(f"👤 Login sebagai:\n{st.user.email}")
if st.sidebar.button("Logout"):
    st.logout()
    st.stop()

# ================================
# FIX PATH UNTUK STREAMLIT CLOUD
# - Tambahkan ROOT repo (bukan folder src) ke sys.path
# ================================
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import controller utama kamu (pakai src.)
from src.controller import controller


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
        return f"❌ Terjadi error saat memproses:\n\n```text\n{e}\n```", ""

    raw = (buf_out.getvalue() or "").strip()
    err = (buf_err.getvalue() or "").strip()
    ret_text = (ret or "").strip()

    if not raw and ret_text:
        raw = ret_text
    elif raw and ret_text and (ret_text not in raw):
        raw = raw + "\n\n" + ret_text

    if err:
        raw = raw + "\n\n```text\n" + err + "\n```"

    content, debug = _split_debug(raw)
    content = _beautify_output(content)

    return content, debug


def _split_debug(text: str) -> Tuple[str, str]:
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
    if not text:
        return text

    text = text.replace("═" * 60, "---")

    import re
    text = re.sub(
        r"\*\*Ayat\s+(\d+)\s+–\s+(.+?)\*\*",
        r"📖 **Surat \2 ayat \1**",
        text
    )

    text = text.replace("**Artinya:**", "📝 **Artinya:**")
    text = text.replace("**Kategori:**", "🧩 **Kategori:**")
    text = text.replace("**Tafsir Kemenag (Tahlili):**", "🟩 **Tafsir Kemenag (Tahlili):**")
    text = text.replace("**Tafsir Kemenag (Wajiz):**", "🟦 **Tafsir Kemenag (Wajiz):**")
    text = text.replace("**Tafsir Buya Hamka:**", "🟥 **Tafsir Buya Hamka:**")

    return text


# ----------------------------
# UI
# ----------------------------
CUSTOM_CSS = """
<style>
.block-container { max-width: 820px; padding-top: 28px; }
[data-testid="stChatMessage"] { padding: 6px 0px; }
.chat-output p, .chat-output li { line-height: 1.6; }
.chat-output hr { margin: 14px 0; }
.hero { text-align: center; margin-bottom: 18px; }
.hero h1 { font-size: 40px; margin: 0; }
.hero p { margin-top: 6px; color: #6b7280; font-size: 14px; }
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
    st.session_state.messages = []

if "show_debug" not in st.session_state:
    st.session_state.show_debug = False

if "preferred_sources" not in st.session_state:
    st.session_state.preferred_sources = ["all"]

# Render message history
for msg in st.session_state.messages:
    avatar = "🧑‍💻" if msg["role"] == "user" else "🕌"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(f"<div class='chat-output'>{msg['content']}</div>", unsafe_allow_html=True)

        if st.session_state.show_debug and msg.get("debug"):
            with st.expander("Lihat debug"):
                st.code(msg["debug"], language="text")

prompt = st.chat_input("Tanyakan sesuatu... (contoh: 'gambaran hisab' atau 'kiamat')")

if prompt:
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
