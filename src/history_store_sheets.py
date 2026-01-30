# src/history_store_sheets.py
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import streamlit as st


@st.cache_resource
def _get_worksheet():
    """
    Connect ke Google Sheets pakai Service Account dari Streamlit Secrets.

    Secrets yang dibutuhkan:
      - GOOGLE_SHEET_NAME (string)
      - GOOGLE_SHEETS_SERVICE_ACCOUNT (string JSON atau object/dict)
    """
    import gspread
    from google.oauth2.service_account import Credentials

    # --- Read secrets ---
    sa_raw = st.secrets.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", None)
    if not sa_raw:
        raise RuntimeError("GOOGLE_SHEETS_SERVICE_ACCOUNT belum diisi di Secrets.")

    sheet_name = st.secrets.get("GOOGLE_SHEET_NAME", None)
    if not sheet_name:
        raise RuntimeError("GOOGLE_SHEET_NAME belum diisi di Secrets.")

    # --- Parse service account (robust) ---
    sa_info = None
    try:
        # Case 1: already a dict-like object
        if isinstance(sa_raw, dict):
            sa_info = sa_raw
        else:
            # Case 2: treat as string JSON
            sa_text = str(sa_raw).strip()

            # anti "Extra data" dari paste dobel -> ambil dari '{' pertama sampai '}' terakhir
            first = sa_text.find("{")
            last = sa_text.rfind("}")
            if first != -1 and last != -1 and last > first:
                sa_text = sa_text[first:last + 1].strip()

            sa_info = json.loads(sa_text)

    except Exception as e:
        raise RuntimeError(
            "Service Account JSON invalid. Pastikan di Secrets kamu hanya ada 1 JSON utuh "
            "di dalam triple quotes.\n"
            f"Detail: {e}"
        )

    # --- Validate required fields ---
    required = ["client_email", "private_key", "token_uri"]
    missing = [k for k in required if k not in sa_info]
    if missing:
        raise RuntimeError(f"Service Account missing fields: {missing}")

    # --- Authorize ---
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)

    # Open file by name, use first worksheet
    sh = gc.open(str(sheet_name))
    return sh.sheet1


def get_user_id() -> str:
    """
    Ambil ID unik user dari Google login.
    Prioritas: st.user.sub -> email -> anonymous
    """
    sub = getattr(st.user, "sub", None)
    email = getattr(st.user, "email", None)

    if sub:
        return str(sub)
    if email:
        return str(email).lower()
    return "anonymous"


def ensure_header(ws) -> None:
    """
    Pastikan header ada di baris pertama.
    """
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
    ws = _get_worksheet()
    ensure_header(ws)

    row = [
        datetime.now(timezone.utc).isoformat(),
        str(user_id),
        str(email),
        str(query),
        str(answer),
        str(session_id or ""),
    ]
    ws.append_row(row, value_input_option="RAW")


def load_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    ws = _get_worksheet()
    ensure_header(ws)

    rows = ws.get_all_records()
    uid = str(user_id)
    mine = [r for r in rows if str(r.get("user_id", "")) == uid]
    mine.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return mine[:limit]


def clear_history(user_id: str) -> int:
    ws = _get_worksheet()
    ensure_header(ws)

    values = ws.get_all_values()
    if not values:
        return 0

    header = values[0]
    data = values[1:]

    kept = []
    removed = 0
    uid = str(user_id)

    for row in data:
        # user_id ada di kolom index 1
        if len(row) > 1 and str(row[1]) == uid:
            removed += 1
        else:
            kept.append(row)

    ws.clear()
    ws.append_row(header, value_input_option="RAW")
    if kept:
        ws.append_rows(kept, value_input_option="RAW")

    return removed
