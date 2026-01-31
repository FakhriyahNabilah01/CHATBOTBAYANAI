# src/history_store_sheets.py
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from collections.abc import Mapping

import streamlit as st


@st.cache_resource
def _get_worksheet():
    """
    Connect ke Google Sheets pakai Service Account dari Streamlit Secrets.
    Return worksheet pertama (tab pertama).
    """
    import gspread
    from google.oauth2.service_account import Credentials

    # WAJIB: nama key harus sama persis dengan di Streamlit Secrets
    sa_raw = st.secrets.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", None)
    if not sa_raw:
        raise RuntimeError("GOOGLE_SHEETS_SERVICE_ACCOUNT belum diisi di Streamlit Secrets.")

    sheet_name = st.secrets.get("GOOGLE_SHEETS_NAME", "")
    if not sheet_name:
        raise RuntimeError("GOOGLE_SHEETS_NAME belum diisi di Streamlit Secrets.")

    # Streamlit Secrets bisa mengembalikan Mapping (dict-like) kalau pakai [SECTION],
    # atau string JSON kalau disimpan sebagai string.
    if isinstance(sa_raw, Mapping):
        sa_info = dict(sa_raw)
    else:
        try:
            sa_info = json.loads(sa_raw)
        except Exception as e:
            raise RuntimeError(
                "GOOGLE_SHEETS_SERVICE_ACCOUNT formatnya bukan JSON yang valid. "
                "Kalau kamu pakai [GOOGLE_SHEETS_SERVICE_ACCOUNT] di Secrets, pastikan itu SECTION TOML yang benar."
            ) from e

    # Kadang private_key kebaca sebagai literal "\\n" — harus jadi newline beneran
    if "private_key" in sa_info and isinstance(sa_info["private_key"], str):
        sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open(sheet_name)
    return sh.sheet1  # tab pertama


def get_user_id() -> str:
    """ID user untuk memisahkan history per akun (sub -> email -> anonymous)."""
    sub = getattr(st.user, "sub", None)
    email = getattr(st.user, "email", None)

    if sub:
        return str(sub)
    if email:
        return str(email).lower()
    return "anonymous"


def ensure_header() -> None:
    """Pastikan header baris pertama ada."""
    ws = _get_worksheet()
    expected = ["created_at", "user_id", "email", "query", "answer", "session_id"]

    values = ws.get_all_values()
    if values and values[0] == expected:
        return

    if not values:
        ws.append_row(expected, value_input_option="RAW")
    else:
        ws.insert_row(expected, index=1)


def save_history(
    user_id: str,
    email: str,
    query: str,
    answer: str,
    session_id: Optional[str] = None
) -> None:
    """Simpan 1 item history ke Google Sheets."""
    ensure_header()
    ws = _get_worksheet()

    created_at = datetime.now(timezone.utc).isoformat()
    row = [created_at, user_id, email, query, answer, session_id or ""]
    ws.append_row(row, value_input_option="RAW")


def load_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Ambil history milik user tertentu (paling baru dulu)."""
    ensure_header()
    ws = _get_worksheet()

    rows = ws.get_all_records()
    mine = [r for r in rows if str(r.get("user_id", "")) == str(user_id)]
    mine.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return mine[:limit]


def clear_history(user_id: str) -> int:
    """Hapus history user, return jumlah terhapus."""
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
        row_user_id = row[1] if len(row) > 1 else ""
        if str(row_user_id) == user_id_str:
            removed += 1
        else:
            kept.append(row)

    ws.clear()
    ws.append_row(header, value_input_option="RAW")
    if kept:
        ws.append_rows(kept, value_input_option="RAW")

    return removed
