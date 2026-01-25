from typing import List, Dict, Any

def format_ayat_record(record, mode: str = "full", tafsir_filter: str = "all"):
    """
    Format output ayat - SEMUA DATA DARI DATASET DITAMPILKAN LENGKAP.
    Tidak ada truncation/pemotongan apapun.
    """
    if not record:
        return "Data tidak ditemukan."

    # HEADER - AMBIL DARI DATASET
    narasi = (
        f"**Ayat {record.get('ayat', '')} dari Surat {record.get('nama_surat', '')}:**\n"
        f"{record.get('arab_ayat', '')}\n"
    )

    # TERJEMAHAN - FULL TEXT DARI DATASET
    if record.get("terjemahan"):
        narasi += f"\n**Artinya:**\n{record['terjemahan']}\n"

    # KATEGORI - FULL LIST DARI DATASET
    if record.get("kategori"):
        kategori = [k.strip() for k in record["kategori"] if k and k.strip()]
        if kategori:
            narasi += f"\n**Kategori:** {', '.join(kategori)}\n"

    # MODE SIMPLE = STOP DI SINI
    if mode == "simple":
        return narasi

    # TAFSIR - TAMPILKAN SESUAI FILTER, FULL TEXT DARI DATASET
    if tafsir_filter == "tahlili":
        if record.get("tafsir_kemenag_tahlili"):
            narasi += (
                "\n**Tafsir Kemenag (Tahlili):**\n"
                f"{record['tafsir_kemenag_tahlili']}\n"
            )

    elif tafsir_filter == "wajiz":
        if record.get("tafsir_kemenag_wajiz"):
            narasi += (
                "\n**Tafsir Kemenag (Wajiz):**\n"
                f"{record['tafsir_kemenag_wajiz']}\n"
            )

    elif tafsir_filter == "hamka":
        if record.get("tafsir_buya_hamka"):
            narasi += (
                "\n**Tafsir Buya Hamka:**\n"
                f"{record['tafsir_buya_hamka']}\n"
            )

    elif tafsir_filter == "all":
        # TAMPILKAN SEMUA TAFSIR YANG ADA, FULL TEXT
        if record.get("tafsir_kemenag_tahlili"):
            narasi += (
                "\n**Tafsir Kemenag (Tahlili):**\n"
                f"{record['tafsir_kemenag_tahlili']}\n"
            )

        if record.get("tafsir_kemenag_wajiz"):
            narasi += (
                "\n**Tafsir Kemenag (Wajiz):**\n"
                f"{record['tafsir_kemenag_wajiz']}\n"
            )

        if record.get("tafsir_buya_hamka"):
            narasi += (
                "\n**Tafsir Buya Hamka:**\n"
                f"{record['tafsir_buya_hamka']}\n"
            )

    return narasi

def format_ayat_narasi_table(item: dict) -> str:
    if not item:
        return "Data tidak ditemukan."

    rows = []

    # Header utama
    rows.append(("Surat", item.get("nama_surat", "-")))
    rows.append(("Ayat", item.get("ayat_ke", "-")))
    rows.append(("Teks Arab", item.get("ayat_arab", "-")))

    if item.get("terjemahan"):
        rows.append(("Terjemahan", item["terjemahan"].strip()))

    if item.get("kategori"):
        kategori = [k for k in item["kategori"] if k]
        if kategori:
            rows.append(("Kategori", ", ".join(kategori)))

    if item.get("tafsir_tahlili"):
        rows.append(("Tafsir Kemenag (Tahlili)", item["tafsir_tahlili"]))

    if item.get("tafsir_wajiz"):
        rows.append(("Tafsir Kemenag (Wajiz)", item["tafsir_wajiz"]))

    if item.get("tafsir_hamka"):
        rows.append(("Tafsir Buya Hamka", item["tafsir_hamka"]))

    # Bangun markdown table
    table = ["| Bagian | Isi |", "|---|---|"]
    for k, v in rows:
        safe_v = str(v).replace("\n", "<br>")
        table.append(f"| **{k}** | {safe_v} |")

    return "\n".join(table)

def _pick(d: Dict[str, Any], *keys: str, default=None):
    """Ambil value dari beberapa kemungkinan nama key."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return default

def format_ayat_narasi_chat(item: Dict[str, Any]) -> str:
    # ambil nama surat + ayat ke dengan fallback beberapa key
    nama_surat = _pick(item, "nama_surat", "Surat", "surat", default="UNKNOWN")
    ayat_ke = _pick(item, "ayat_ke", "AyatKe", "ayatKe", "ayat_ke_int", default="?")

    # rapihin ayat_ke jadi angka kalau bisa
    try:
        ayat_ke_str = str(int(ayat_ke))
    except Exception:
        ayat_ke_str = str(ayat_ke) if ayat_ke is not None else "?"

    arab_ayat = _pick(item, "arab_ayat", "Ayat", "arab", default="").strip()
    terjemahan = _pick(item, "terjemahan", "Terjemahan", default="").strip()

    kategori = _pick(item, "kategori", "Kategori", default=[])
    if kategori is None:
        kategori = []
    if isinstance(kategori, str):
        kategori = [kategori]

    tafsir_tahlili = _pick(item, "tafsir_kemenag_tahlili", "tafsir_tahlili", default=None)
    tafsir_wajiz   = _pick(item, "tafsir_kemenag_wajiz", "tafsir_wajiz", default=None)
    tafsir_hamka   = _pick(item, "tafsir_buya_hamka", "tafsir_hamka", default=None)

    lines: List[str] = []
    lines.append(f"📖 **Surat {nama_surat} ayat {ayat_ke_str}**")

    if arab_ayat:
        lines.append(arab_ayat)

    if terjemahan:
        lines.append(f"**Artinya:** {terjemahan}")

    kategori_clean = [k.strip() for k in kategori if isinstance(k, str) and k.strip()]
    if kategori_clean:
        lines.append(f"**Kategori:** {', '.join(kategori_clean)}")

    if tafsir_tahlili:
        lines.append("\n**Tafsir Kemenag (Tahlili):**")
        lines.append(str(tafsir_tahlili).strip())

    if tafsir_wajiz:
        lines.append("\n**Tafsir Kemenag (Wajiz):**")
        lines.append(str(tafsir_wajiz).strip())

    if tafsir_hamka:
        lines.append("\n**Tafsir Buya Hamka:**")
        lines.append(str(tafsir_hamka).strip())

    return "\n".join(lines)

def format_list(results: List[Dict[str, Any]], start_index: int = 0) -> str:
    if not results:
        return "Tidak ditemukan ayat yang relevan."

    lines = ["Ditemukan ayat yang relevan:"]
    for i, it in enumerate(results, 1):
        lines.append(f"{i}. Surat {it.get('nama_surat','-')} ayat {it.get('ayat_ke','-')}")

    lines.append("\nKetik: 'tambah 5' untuk menambah hasil, atau 'lanjutkan' untuk tampilkan lagi.")
    return "\n".join(lines)

