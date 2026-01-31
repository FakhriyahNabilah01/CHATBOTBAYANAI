# src/history_store_sheets.py
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import streamlit as st


@st.cache_resource
def _get_worksheet():
    """
    Connect ke Google Sheets pakai Service Account dari Streamlit Secrets.
    Support 2 format Secrets:
    1) String JSON (triple quotes)
    2) TOML object (dict)
    """
    import gspread
    from google.oauth2.service_account import Credentials

    # ---- ambil service account dari secrets (bisa string atau dict)
    sa_val = st.secrets.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", None)
    if sa_val is None or sa_val == "":
        raise RuntimeError(
            f"GOOGLE_SHEETS_SERVICE_ACCOUNT belum diisi di Secrets. Keys yang terbaca: {list(st.secrets.keys())}"
        )

    # ---- sheet name (kita support 2 nama biar gak mismatch)
    sheet_name = (
        st.secrets.get("GOOGLE_SHEET_NAME", "")
        or st.secrets.get("GOOGLE_SHEETS_NAME", "")
    )
    if not sheet_name:
        raise RuntimeError("Sheet name belum diisi. Pakai GOOGLE_SHEET_NAME di Secrets.")

    # ---- parse service account
    if isinstance(sa_val, str):
        sa_info = json.loads(sa_val)   # format triple quotes string JSON
    elif isinstance(sa_val, dict):
        sa_info = dict(sa_val)         # format toml object
    else:
        raise RuntimeError(f"Format GOOGLE_SHEETS_SERVICE_ACCOUNT tidak dikenali: {type(sa_val)}")

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
