# src/search_flow.py
from typing import List, Dict, Any, Optional, Union

from neo4j_client import get_ayat
from formatter import format_ayat_narasi_chat


def _normalize_focus(focus: Union[None, str, List[str]]) -> Optional[str]:
    """
    Normalisasi focus agar menjadi string sederhana:
    - None -> None
    - "hamka" -> "hamka"
    - ["hamka"] -> "hamka"
    """
    if not focus:
        return None
    if isinstance(focus, str):
        return focus.strip().lower()
    if isinstance(focus, list) and focus:
        return str(focus[0]).strip().lower()
    return None


def _normalize_record_keys(rec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pastikan record dari DB punya key standar yang dipakai formatter:
    - nama_surat
    - ayat_ke
    - arab_ayat
    - terjemahan
    - kategori
    - tafsir_tahlili / tafsir_wajiz / tafsir_hamka (kalau ada)
    """
    if not rec:
        return rec

    # --- surat & ayat_ke ---
    if "nama_surat" not in rec or rec.get("nama_surat") is None:
        rec["nama_surat"] = rec.get("Surat") or rec.get("surat") or "UNKNOWN"

    if "ayat_ke" not in rec or rec.get("ayat_ke") is None:
        rec["ayat_ke"] = rec.get("AyatKe") or rec.get("ayatKe") or rec.get("ayat_ke_int")

    # paksa ayat_ke jadi int kalau bisa
    try:
        if rec.get("ayat_ke") is not None and rec.get("ayat_ke") != "?":
            rec["ayat_ke"] = int(rec["ayat_ke"])
    except Exception:
        pass

    # --- arab & terjemahan ---
    if "arab_ayat" not in rec or rec.get("arab_ayat") is None:
        rec["arab_ayat"] = rec.get("Ayat") or rec.get("arab") or ""

    if "terjemahan" not in rec or rec.get("terjemahan") is None:
        rec["terjemahan"] = rec.get("Terjemahan") or ""

    # --- kategori ---
    if "kategori" not in rec or rec.get("kategori") is None:
        rec["kategori"] = rec.get("Kategori") or []

    # kategori kadang string -> ubah jadi list
    if isinstance(rec.get("kategori"), str):
        rec["kategori"] = [rec["kategori"]]

    # --- normalisasi tafsir keys (biar konsisten dipakai di formatter) ---
    if "tafsir_tahlili" not in rec or rec.get("tafsir_tahlili") is None:
        rec["tafsir_tahlili"] = rec.get("tafsir_kemenag_tahlili")

    if "tafsir_wajiz" not in rec or rec.get("tafsir_wajiz") is None:
        rec["tafsir_wajiz"] = rec.get("tafsir_kemenag_wajiz")

    if "tafsir_hamka" not in rec or rec.get("tafsir_hamka") is None:
        rec["tafsir_hamka"] = rec.get("tafsir_buya_hamka")

    return rec


def apply_source_filter(record: Dict[str, Any], source: str) -> Dict[str, Any]:
    """
    Filter output tafsir sesuai permintaan user.
    PENTING: jangan pernah hilangkan nama_surat & ayat_ke.
    """
    src = (source or "").lower().strip()

    base = {
        "nama_surat": record.get("nama_surat"),
        "ayat_ke": record.get("ayat_ke"),
        "arab_ayat": record.get("arab_ayat"),
        "terjemahan": record.get("terjemahan"),
        "kategori": record.get("kategori") or [],
    }

    if src in ("hamka", "buya_hamka", "tafsir_hamka"):
        base["tafsir_hamka"] = record.get("tafsir_hamka")
        return base

    if src in ("wajiz", "kemenag_wajiz", "tafsir_wajiz"):
        base["tafsir_wajiz"] = record.get("tafsir_wajiz")
        return base

    if src in ("tahlili", "kemenag_tahlili", "tafsir_tahlili"):
        base["tafsir_tahlili"] = record.get("tafsir_tahlili")
        return base

    # default: tidak difilter
    return record


def format_many(results: List[Dict[str, Any]], focus: Union[None, str, List[str]] = None) -> str:
    """
    Ubah list hasil search (yang biasanya cuma punya nama_surat + ayat_ke + score)
    menjadi narasi lengkap per ayat (ambil full record via get_ayat).
    """
    if not results:
        return "Tidak ditemukan ayat yang relevan."

    source = _normalize_focus(focus)
    blocks: List[str] = []

    for it in results:
        nama_surat = it.get("nama_surat")
        ayat_ke = it.get("ayat_ke")

        if not nama_surat or ayat_ke is None:
            continue  # skip data rusak

        # Ambil data lengkap ayat dari DB
        record = get_ayat(nama_surat, int(ayat_ke))
        if not record:
            continue

        # pastikan key konsisten
        record = _normalize_record_keys(record)

        # filter tafsir bila ada focus
        if source:
            record = apply_source_filter(record, source)

        blocks.append(format_ayat_narasi_chat(record))

    return "\n\n---\n\n".join(blocks) if blocks else "Tidak ditemukan ayat yang relevan."
