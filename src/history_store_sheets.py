# src/history_store_sheets.py
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import streamlit as st


@st.cache_resource
def _get_worksheet():
    """
    Connect ke Google Sheets pakai Service Account dari Streamlit Secrets.
    """
    import gspread
    from google.oauth2.service_account import Credentials

    sa_raw = st.secrets.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", "")
    if not sa_raw:
        raise RuntimeError("GOOGLE_SHEETS_SERVICE_ACCOUNT belum diisi di Secrets.")

    sheet_name = st.secrets.get("GOOGLE_SHEET_NAME", "")
    if not sheet_name:
        raise RuntimeError("GOOGLE_SHEET_NAME belum diisi di Secrets.")

    sa_info = st.secrets["GOOGLE_SHEETS_SERVICE_ACCOUNT"]

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open(sheet_name)
    return sh.sheet1


def get_user_id() -> str:
    """
    Ambil ID unik user dari Google login.
    """
    sub = getattr(st.user, "sub", None)
    email = getattr(st.user, "email", None)

    if sub:
        return str(sub)
    if email:
        return email.lower()
    return "anonymous"


def ensure_header() -> None:
    ws = _get_worksheet()
    header = ["created_at", "user_id", "email", "query", "answer", "session_id"]

    values = ws.get_all_values()
    if values and values[0] == header:
        return

    if not values:
        ws.append_row(header, value_input_option="RAW")
    else:
        ws.insert_row(header, index=1)


def save_history(
    user_id: str,
    email: str,
    query: str,
    answer: str,
    session_id: Optional[str] = None
) -> None:
    ensure_header()
    ws = _get_worksheet()

    row = [
        datetime.now(timezone.utc).isoformat(),
        user_id,
        email,
        query,
        answer,
        session_id or "",
    ]
    ws.append_row(row, value_input_option="RAW")


def load_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    ensure_header()
    ws = _get_worksheet()

    rows = ws.get_all_records()
    mine = [r for r in rows if str(r.get("user_id")) == str(user_id)]
    mine.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return mine[:limit]


def clear_history(user_id: str) -> int:
    ensure_header()
    ws = _get_worksheet()

    values = ws.get_all_values()
    if not values:
        return 0

    header = values[0]
    data = values[1:]

    kept = []
    removed = 0

    for row in data:
        if len(row) > 1 and str(row[1]) == str(user_id):
            removed += 1
        else:
            kept.append(row)

    ws.clear()
    ws.append_row(header, value_input_option="RAW")
    if kept:
        ws.append_rows(kept, value_input_option="RAW")

    return removed
