import os
import re
import requests
from io import StringIO
from contextlib import redirect_stdout
from fastapi import FastAPI, Request, HTTPException

# PASTIKAN import ini sesuai struktur project kamu
from src.controller import controller

app = FastAPI()

WAHA_BASE_URL = os.getenv("WAHA_BASE_URL", "http://localhost:3001").rstrip("/")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")  # bebas (buat security)
MAX_WA_CHARS = int(os.getenv("MAX_WA_CHARS", "3500"))


def _headers():
    h = {"Content-Type": "application/json"}
    if WAHA_API_KEY:
        h["X-Api-Key"] = WAHA_API_KEY
    return h


def send_text(chat_id: str, text: str):
    """
    WAHA sendText payload:
    {session, chatId, text}
    """
    url = f"{WAHA_BASE_URL}/api/sendText"
    payload = {"session": WAHA_SESSION, "chatId": chat_id, "text": text}
    r = requests.post(url, headers=_headers(), json=payload, timeout=60)

    # Biar kelihatan jelas kalau WAHA nolak (mis. session belum WORKING)
    try:
        r.raise_for_status()
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"WAHA sendText failed: {e} | status={getattr(r, 'status_code', '-')}, body={getattr(r, 'text', '-')}",
        )

    return r.json()


def clean_output(s: str) -> str:
    # buang noise debug biar jawaban WA rapi
    out_lines = []
    for line in (s or "").splitlines():
        if (
            line.startswith("[DEBUG]")
            or line.startswith("[DEDUP")
            or "Received notification" in line
        ):
            continue
        out_lines.append(line.rstrip())
    out = "\n".join(out_lines).strip()
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def split_message(s: str, max_len: int):
    s = s or ""
    if len(s) <= max_len:
        return [s]
    parts = []
    rest = s
    while rest:
        chunk = rest[:max_len]
        cut = chunk.rfind("\n")
        if cut < int(max_len * 0.6):
            cut = max_len
        parts.append(rest[:cut].strip())
        rest = rest[cut:].lstrip()
    return parts


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/waha/webhook")
async def waha_webhook(req: Request):
    # security sederhana: set token di url webhook
    if WEBHOOK_TOKEN:
        token = req.query_params.get("token")
        if token != WEBHOOK_TOKEN:
            raise HTTPException(401, "Invalid token")

    body = await req.json()
    event = body.get("event") or body.get("type")
    payload = body.get("payload") or {}

    # kalau bukan event message, skip
    if event and event != "message":
        return {"ok": True}

    # cegah loop balas pesan sendiri
    if payload.get("fromMe") is True:
        return {"ok": True}

    text = (payload.get("body") or payload.get("text") or "").strip()
    chat_id = payload.get("chatId") or payload.get("from")

    if not text or not chat_id:
        return {"ok": True}

    # pakai chat_id jadi session_id biar state "lanjut" per user WA jalan
    try:
        buf = StringIO()
        with redirect_stdout(buf):
            ret = controller(text, session_id=str(chat_id))

        # ✅ PRIORITAS: return string dari controller
        # ✅ FALLBACK: kalau controller print, ambil dari stdout buffer
        reply_raw = ret if isinstance(ret, str) and ret.strip() else buf.getvalue()
        reply = clean_output(reply_raw)

    except Exception as e:
        reply = f"Maaf, sistem error: {type(e).__name__}: {e}"

    if not reply:
        reply = "Maaf, aku belum nemu jawaban yang pas. Coba tanya dengan kata lain ya."

    print("DEBUG_REPLY_LEN:", len(reply))
    print("DEBUG_REPLY_PREVIEW:", reply[:200])

    for part in split_message(reply, MAX_WA_CHARS):
        send_text(str(chat_id), part)

    return {"ok": True}
