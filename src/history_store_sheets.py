# src/history_store_sheets.py
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import streamlit as st


@st.cache_resource
def _get_worksheet():
    """
    Connect ke Google Sheets pakai Service Account dari Streamlit Secrets.
    Return worksheet pertama (sheet/tab pertama).
    """
    import gspread
    from google.oauth2.service_account import Credentials

    sa_raw = st.secrets.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", "")
    if not sa_raw:
        raise RuntimeError("GOOGLE_SHEETS_SERVICE_ACCOUNT belum diisi di Streamlit Secrets.")

    sheet_name = st.secrets.get("GOOGLE_SHEET_NAME", "")
    if not sheet_name:
        raise RuntimeError("GOOGLE_SHEET_NAME belum diisi di Streamlit Secrets.")

    sa_info = json.loads(sa_raw)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open(sheet_name)
    ws = sh.sheet1  # worksheet/tab pertama
    return ws


def get_user_id() -> str:
    """
    ID user untuk memisahkan history per akun.
    Prioritas: sub (unik) -> email.
    """
    sub = getattr(st.user, "sub", None)
    email = getattr(st.user, "email", None)

    if sub:
        return str(sub)
    if email:
        return str(email).lower()
    return "anonymous"


def ensure_header() -> None:
    """
    Pastikan header baris pertama ada:
    created_at | user_id | email | query | answer | session_id
    Kalau sudah ada, tidak ngapa-ngapain.
    """
    ws = _get_worksheet()
    expected = ["created_at", "user_id", "email", "query", "answer", "session_id"]

    values = ws.get_all_values()
    if values and values[0] == expected:
        return

    # Kalau sheet kosong, tulis header
    if not values:
        ws.append_row(expected, value_input_option="RAW")
        return

    # Kalau ada data tapi header tidak sesuai, tetap tambahkan header di baris 1 (lebih aman)
    ws.insert_row(expected, index=1)


def save_history(
    user_id: str,
    email: str,
    query: str,
    answer: str,
    session_id: Optional[str] = None
) -> None:
    """
    Simpan 1 item history ke Google Sheets.
    """
    ensure_header()
    ws = _get_worksheet()

    created_at = datetime.now(timezone.utc).isoformat()
    row = [created_at, user_id, email, query, answer, session_id or ""]
    ws.append_row(row, value_input_option="RAW")


def load_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Ambil history milik user tertentu (paling baru dulu).
    Karena Sheets tidak punya query seperti DB, kita filter di Python.
    """
    ensure_header()
    ws = _get_worksheet()

    rows = ws.get_all_records()  # list[dict] berdasarkan header
    # Filter milik user
    mine = [r for r in rows if str(r.get("user_id", "")) == str(user_id)]

    # Urutkan terbaru
    mine.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    return mine[:limit]


def clear_history(user_id: str) -> int:
    """
    Hapus history user (cara aman: rebuild sheet tanpa rows milik user).
    Return jumlah yang terhapus.
    """
    ensure_header()
    ws = _get_worksheet()

    values = ws.get_all_values()
    if not values:
        return 0

    header = values[0]
    data = values[1:]

    kept = []
    removed = 0
    user_id_str = str(user_id)

    for row in data:
        # Pastikan panjang row aman
        row_user_id = row[1] if len(row) > 1 else ""
        if str(row_user_id) == user_id_str:
            removed += 1
        else:
            kept.append(row)

    # Clear dan tulis ulang
    ws.clear()
    ws.append_row(header, value_input_option="RAW")
    if kept:
        ws.append_rows(kept, value_input_option="RAW")

    return removed
