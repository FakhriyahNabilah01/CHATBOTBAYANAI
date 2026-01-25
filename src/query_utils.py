# src/query_utils.py
from __future__ import annotations

import re
from typing import Optional, Set


# =========================
# Basic helpers (NEW)
# =========================
def normalize_surat_name(name: str) -> str:
    """
    Normalisasi nama surat agar konsisten:
    - UPPERCASE
    - spasi jadi '-'
    - hapus tanda kutip ' dan `
    """
    if not name:
        return ""
    return (
        str(name)
        .upper()
        .replace(" ", "-")
        .replace("'", "")
        .replace("`", "")
        .strip()
    )


def detect_sources(text: str) -> Set[str]:
    """
    Deteksi filter tafsir dari input user.
    Output: {"all"} / {"hamka"} / {"tahlili"} / {"wajiz"} (bisa juga gabungan).
    """
    text = (text or "").lower()
    sources: Set[str] = set()

    if any(k in text for k in ["tahlili", "kemenag tahlili", "tafsir tahlili"]):
        sources.add("tahlili")

    if any(k in text for k in ["wajiz", "kemenag wajiz", "tafsir wajiz"]):
        sources.add("wajiz")

    if any(k in text for k in ["hamka", "buya hamka", "tafsir hamka"]):
        sources.add("hamka")

    if any(k in text for k in ["semua", "lengkap", "full", "all"]):
        sources.add("all")

    return sources if sources else {"all"}


def extract_number_natural(text: str) -> Optional[int]:
    """
    Ambil angka dari teks:
    - Bisa digit: "lanjut 10"
    - Bisa kata: "lanjut sepuluh"
    Return: int atau None
    """
    text = (text or "").lower().strip()

    number_words = {
        "nol": 0, "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
        "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10,
        "sebelas": 11, "dua belas": 12, "tiga belas": 13, "empat belas": 14,
        "lima belas": 15, "enam belas": 16, "tujuh belas": 17, "delapan belas": 18,
        "sembilan belas": 19, "dua puluh": 20, "tiga puluh": 30, "empat puluh": 40,
        "lima puluh": 50, "seratus": 100,
    }

    # digit dulu
    m = re.search(r"\b(\d{1,4})\b", text)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None

    # kata angka (frasa panjang dulu)
    for phrase, value in sorted(number_words.items(), key=lambda x: -len(x[0])):
        if phrase in text:
            return value

    return None


def is_lanjut_cmd(text: str) -> bool:
    """
    Deteksi perintah 'lanjut' / 'next' / 'tambah' / 'lebih'
    """
    lower = (text or "").lower().strip()
    return lower.startswith("lanjut") or lower in {"lanjut", "next", "tambah", "lebih"}


# =========================
# Enrichment (EXISTING)
# =========================
def enrich_topic_with_terminology(user_text: str, original_topic: str) -> str:
    kiamat_terms = {
        "yaum ad-din": "Yaum ad-Dīn (Hari Pembalasan)",
        "yaum al-din": "Yaum ad-Dīn (Hari Pembalasan)",
        "yaumul din": "Yaum ad-Dīn (Hari Pembalasan)",
        "hari pembalasan": "Hari Pembalasan (Yaum ad-Dīn)",

        "yaum al-khulud": "Yaum al-Khulūd (Hari Keabadian)",
        "yaum al-khulūd": "Yaum al-Khulūd (Hari Keabadian)",
        "yaumul khulud": "Yaum al-Khulūd (Hari Keabadian)",
        "hari keabadian": "Hari Keabadian (Yaum al-Khulūd)",

        "yaum al-qiyamah": "Yaum al-Qiyāmah (Hari Kiamat)",
        "yaum al-qiyāmah": "Yaum al-Qiyāmah (Hari Kiamat)",
        "yaumul qiyamah": "Yaum al-Qiyāmah (Hari Kiamat)",
        "hari kiamat": "Hari Kiamat (Yaum al-Qiyāmah)",

        "at-tammah": "Aṭ-Ṭāmmat al-Kubrā (Malapetaka Besar)",
        "at-tammat": "Aṭ-Ṭāmmat al-Kubrā (Malapetaka Besar)",
        "at-tammatul kubra": "Aṭ-Ṭāmmat al-Kubrā (Malapetaka Besar)",
        "malapetaka besar": "Malapetaka Besar (Aṭ-Ṭāmmat al-Kubrā)",

        "al-qari'ah": "Al-Qāri'ah (Ketukan Dahsyat)",
        "al-qāriah": "Al-Qāri'ah (Ketukan Dahsyat)",
        "al-qariah": "Al-Qāri'ah (Ketukan Dahsyat)",
        "ketukan dahsyat": "Ketukan Dahsyat (Al-Qāri'ah)",

        "yaum al-ba'ts": "Yaum al-Ba'ts (Hari Kebangkitan)",
        "yaum al-ba'th": "Yaum al-Ba'ts (Hari Kebangkitan)",
        "yaumul ba'ts": "Yaum al-Ba'ts (Hari Kebangkitan)",
        "hari kebangkitan": "Hari Kebangkitan (Yaum al-Ba'ts)",

        "yaum al-khuruj": "Yaum al-Khurūj (Hari Keluar dari Kubur)",
        "yaum al-khurūj": "Yaum al-Khurūj (Hari Keluar dari Kubur)",
        "yaumul khuruj": "Yaum al-Khurūj (Hari Keluar dari Kubur)",
        "hari keluar": "Hari Keluar dari Kubur (Yaum al-Khurūj)",

        "yaum al-jam'": "Yaum al-Jam' (Hari Berkumpul di Mahsyar)",
        "yaumul jam'": "Yaum al-Jam' (Hari Berkumpul di Mahsyar)",
        "padang mahsyar": "Padang Mahsyar (Yaum al-Jam')",
        "mahsyar": "Padang Mahsyar (Yaum al-Jam')",

        "yaum al-hisab": "Yaum al-Ḥisāb (Hari Perhitungan Amal)",
        "yaum al-ḥisāb": "Yaum al-Ḥisāb (Hari Perhitungan Amal)",
        "yaumul hisab": "Yaum al-Ḥisāb (Hari Perhitungan Amal)",
        "perhitungan amal": "Perhitungan Amal (Yaum al-Ḥisāb)",

        "yaum al-mizan": "Yaum al-Mizan (Hari Penimbangan Amal)",
        "yaum al-mīzān": "Yaum al-Mizan (Hari Penimbangan Amal)",
        "yaumul mizan": "Yaum al-Mizan (Hari Penimbangan Amal)",
        "penimbangan amal": "Penimbangan Amal (Yaum al-Mizan)",
        "mizan": "Mizan (Timbangan Amal)",

        "yaum al-akhir": "Yaum al-Akhir (Hari Akhir)",
        "yaumul akhir": "Yaum al-Akhir (Hari Akhir)",
        "hari akhir": "Hari Akhir (Yaum al-Akhir)",
        "akhirat": "Akhirat",

        "yaum al-fasl": "Yaum al-Faṣl (Hari Pemutusan Perkara)",
        "yaum al-faṣl": "Yaum al-Faṣl (Hari Pemutusan Perkara)",
        "yaumul fasl": "Yaum al-Faṣl (Hari Pemutusan Perkara)",
        "hari pemisahan": "Hari Pemisahan (Yaum al-Faṣl)",

        "as-sakhkhah": "As-Ṣākhkhah (Tiupan Sangkakala)",
        "as-ṣākhkhah": "As-Ṣākhkhah (Tiupan Sangkakala)",
        "as-sakkah": "As-Ṣākhkhah (Tiupan Sangkakala)",
        "as-sakhah": "As-Ṣākhkhah (Tiupan Sangkakala)",
        "as-sakah": "As-Ṣākhkhah (Tiupan Sangkakala)",
        "sangkakala": "Sangkakala (As-Ṣākhkhah)",
        "terompet": "Sangkakala (As-Ṣākhkhah)",

        "yaum al-hasrah": "Yaum al-Ḥasrah (Hari Penyesalan)",
        "yaum al-ḥasrah": "Yaum al-Ḥasrah (Hari Penyesalan)",
        "yaumul hasrah": "Yaum al-Ḥasrah (Hari Penyesalan)",
        "hari penyesalan": "Hari Penyesalan (Yaum al-Ḥasrah)",

        "as-sa'ah": "As-Sā'ah (Waktu yang Pasti Datang)",
        "as-sā'ah": "As-Sā'ah (Waktu yang Pasti Datang)",
        "as-saah": "As-Sā'ah (Waktu yang Pasti Datang)",

        "al-ghashiyah": "Al-Ghāshiyah (Hari yang Menutupi)",
        "al-ghāshiyah": "Al-Ghāshiyah (Hari yang Menutupi)",
        "al-ghasiyah": "Al-Ghāshiyah (Hari yang Menutupi)",

        "jahannam": "Neraka Jahannam",
        "neraka jahannam": "Neraka Jahannam",
        "huthamah": "Neraka Huthamah",
        "neraka huthamah": "Neraka Huthamah",
        "hawiyah": "Neraka Hawiyah",
        "neraka hawiyah": "Neraka Hawiyah",
        "jahim": "Neraka Jahim",
        "neraka jahim": "Neraka Jahim",
    }

    lower_text = (user_text or "").lower()
    sorted_terms = sorted(kiamat_terms.keys(), key=len, reverse=True)
    for term in sorted_terms:
        if term in lower_text:
            return f"{original_topic} {kiamat_terms[term]}"
    return original_topic


def enrich_topic_with_category(user_text: str, original_topic: str) -> str:
    category_mapping = {
        "perintah": "perintah untuk kebaikan dunia dan agama",
        "perintah allah": "perintah Allah untuk kebaikan",
        "kebaikan dunia": "kebaikan dunia dan akhirat",
        "kebaikan akhirat": "kebaikan dunia dan akhirat",
        "kelalaian": "kelalaian manusia terhadap persiapan Hari Akhir",
        "lalai": "kelalaian terhadap Hari Akhir",
        "lupa akhirat": "kelalaian karena sibuk mengejar dunia",
        "sibuk dunia": "kelalaian karena sibuk mengejar dunia",
        "mengejar dunia": "kelalaian karena sibuk mengejar dunia",
        "cinta dunia": "kelalaian karena terlalu cinta dunia",
        "penyesalan": "penyesalan besar bagi orang kafir",
        "menyesal": "penyesalan di Hari Akhir",
        "sesal": "penyesalan besar",
        "ketidakberdayaan": "ketidakberdayaan segala hal duniawi saat menghadapi azab",
        "tidak berguna": "ketidakberdayaan harta dan tahta di Hari Akhir",
        "harta tidak berguna": "ketidakberdayaan harta saat menghadapi azab",
        "tahta tidak berguna": "ketidakberdayaan kekuasaan saat menghadapi azab",
        "dunia tidak berguna": "ketidakberdayaan segala hal duniawi",

        "gambaran kiamat": "gambaran perilaku manusia saat terjadinya hari kiamat",
        "keadaan kiamat": "keadaan manusia ketika datang hari kiamat",
        "saat kiamat": "keadaan manusia saat hari kiamat",
        "ketika kiamat": "keadaan manusia ketika hari kiamat",
        "waktu kiamat": "keadaan manusia di waktu kiamat",

        "balasan baik": "perilaku yang berpotensi mendapat balasan baik di akhirat",
        "surga": "perilaku yang berpotensi mendapat balasan surga",
        "masuk surga": "perilaku yang berpotensi masuk surga",
        "pahala": "perilaku yang mendapat pahala",
        "ganjaran baik": "perilaku yang mendapat ganjaran baik",

        "balasan buruk": "perilaku yang berpotensi mendapat balasan buruk di akhirat",
        "neraka": "perilaku yang berpotensi mendapat balasan neraka",
        "masuk neraka": "perilaku yang berpotensi masuk neraka",
        "siksa": "perilaku yang mendapat siksa",
        "azab": "perilaku yang mendapat azab",

        "amalan baik": "gambaran balasan amalan baik di akhirat",
        "amalan buruk": "gambaran balasan amalan buruk di akhirat",
        "perbuatan baik": "balasan perbuatan baik",
        "perbuatan buruk": "balasan perbuatan buruk",

        "as-sakhkhah": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "as-sakkah": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "as-sakhah": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "as-sakhkha": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "sakhkhah": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "sakkah": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "sakhah": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "sakhkha": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras Hari Kiamat)",
        "ketukan dahsyat": "As-Ṣākhkhah (Ketukan Dahsyat / Tiupan Sangkakala Hari Kiamat)",
        "tiupan sangkakala": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat / Ketukan Keras)",
        "sangkakala dahsyat": "As-Ṣākhkhah (Tiupan Sangkakala Dahsyat)",

        "al-qari'ah": "Al-Qāri'ah (Ketukan Dahsyat / sinonim As-Ṣākhkhah)",
        "al-qariah": "Al-Qāri'ah (Ketukan Dahsyat / sinonim As-Ṣākhkhah)",
        "qari'ah": "Al-Qāri'ah (Ketukan Dahsyat / sinonim As-Ṣākhkhah)",
    }

    lower_text = (user_text or "").lower()
    sorted_cats = sorted(category_mapping.keys(), key=len, reverse=True)
    for cat_key in sorted_cats:
        if cat_key in lower_text:
            return f"{original_topic} {category_mapping[cat_key]}"
    return original_topic


# =========================
# Query type + smart k (EXISTING)
# =========================
def detect_query_type(user_text: str) -> str:
    lower = (user_text or "").lower()

    comparative_keywords = [
        "beda", "bedanya", "perbedaan", "berbeda dengan",
        "vs", "versus", "dibanding", "dibandingkan dengan",
        "mana yang", "lebih", " atau ", "apa bedanya"
    ]
    if any(k in lower for k in comparative_keywords):
        return "comparative"

    process_keywords = [
        "urutan", "proses", "tahapan", "langkah-langkah",
        "mulai dari", "sampai", "hingga", "dari awal",
        "setelah", "kemudian", "lalu", "berikutnya",
        "pertama", "kedua", "ketiga", "terakhir"
    ]
    if any(k in lower for k in process_keywords):
        return "process"

    definition_keywords = [
        "apa itu", "apa sih", "apakah itu",
        "jelaskan apa", "jelasin apa",
        "maksud dari", "arti dari", "makna dari", "definisi"
    ]
    if any(k in lower for k in definition_keywords):
        return "definition"

    category_keywords = [
        "apa saja", "apa aja", "ada apa saja",
        "sebutkan", "tuliskan", "tampilkan",
        "perintah apa", "larangan apa", "perilaku apa",
        "yang dilarang", "yang diperintahkan"
    ]
    if any(k in lower for k in category_keywords):
        return "category"

    very_general_keywords = [
        "ceritain", "cerita tentang", "kasih tau tentang",
        "jelaskan tentang", "jelasin tentang",
        "apa yang ada di", "konten", "isi"
    ]
    if any(k in lower for k in very_general_keywords):
        return "general"

    return "specific"


def get_smart_search_limit(user_text: str, default: int = 20) -> int:
    lower = (user_text or "").lower()

    if any(k in lower for k in ["beda", "perbedaan", "vs", "dibanding", "atau"]):
        return 100
    if any(k in lower for k in ["semua", "seluruh", "lengkap", "keseluruhan"]):
        return 100
    if any(k in lower for k in ["urutan", "proses", "tahapan"]):
        return 50
    if any(k in lower for k in ["apa itu", "jelaskan tentang", "maksud dari"]):
        return 100

    return default


def extract_n(user_text: str) -> int:
    """
    Ambil angka dari pola:
    - "tambah 5"
    - "lanjut 10"
    - "5 lagi"
    Return 0 kalau tidak ketemu.
    """
    patterns = [
        r"tambah(?:kan)?\s+(\d+)",
        r"lanjut(?:kan)?\s+(\d+)",
        r"tambahin\s+(\d+)",
        r"(\d+)\s+(?:lagi|ayat)",
        r"minta\s+(\d+)",
        r"kasih\s+(\d+)",
        r"load\s+(\d+)",
        r"show\s+(\d+)",
        r"(?:next|berikutnya)\s+(\d+)",
    ]

    text = (user_text or "").lower()
    for pattern in patterns:
        match = re.search(pattern, text)
        if match and match.lastindex and match.lastindex >= 1:
            try:
                return int(match.group(1))
            except ValueError:
                continue
    return 0


def fallback_extract_more_n(text: str, default: int = 5) -> int:
    """
    Dipakai kalau user bilang "lanjut / tambah" tapi tidak jelas angkanya.
    """
    n = extract_n(text)
    if n > 0:
        return n

    n2 = extract_number_natural(text)
    if n2 and n2 > 0:
        return n2

    return default


def get_smart_ayat_count(user_text: str, available: int, default: int = 10) -> int:
    """
    Menentukan jumlah ayat awal yang ditampilkan berdasarkan input user.
    - Default: 10 ayat
    - Kalau ada angka eksplisit → pakai itu (maks available)
    - Kalau minta "semua/lengkap" → tampilkan semua hasil
    - Kalau pertanyaan penjelasan ("apa itu", "jelaskan") → 5 ayat
    """
    try:
        lower = (user_text or "").lower()
        n = extract_n(user_text)

        if n > 0:
            return min(n, available)

        if any(k in lower for k in ["semua", "seluruh", "lengkap", "keseluruhan", "full"]):
            return available

        if any(k in lower for k in ["apa itu", "jelaskan tentang", "maksud dari", "apa maksud", "apa artinya"]):
            return min(5, available)

        if any(k in lower for k in ["beda", "perbedaan", "vs", "dibanding", "bandingkan"]):
            return min(8, available)

        return min(default, available)

    except Exception as e:
        print(f"[ERROR] get_smart_ayat_count gagal: {e} → return default {default}")
        return min(default, available)


# =========================
# Narration (EXISTING)
# =========================
def generate_opening_narration(intent: str, topic: str, user_text: str) -> str:
    if intent == "continue":
        return f"Baik, melanjutkan dari topik sebelumnya: {topic}.\n\n"

    lower = (user_text or "").lower()
    narrations = {
        "hari kebangkitan": "tentang hari kebangkitan",
        "hari kiamat": "tentang hari kiamat",
        "surga": "tentang surga",
        "neraka": "tentang neraka",
        "shalat": "tentang shalat",
        "zakat": "tentang zakat",
        "puasa": "tentang puasa",
        "doa": "tentang doa",
        "sabar": "tentang kesabaran",
        "taubat": "tentang taubat",
        "rezeki": "tentang rezeki",
        "takwa": "tentang takwa",
        "iman": "tentang iman",

        "yaum ad-din": "tentang Hari Pembalasan (Yaum ad-Dīn)",
        "yaumul din": "tentang Hari Pembalasan (Yaum ad-Dīn)",
        "hari pembalasan": "tentang Hari Pembalasan",

        "yaum al-khulud": "tentang Hari Keabadian (Yaum al-Khulūd)",
        "yaumul khulud": "tentang Hari Keabadian",
        "hari keabadian": "tentang Hari Keabadian",

        "yaum al-qiyamah": "tentang Hari Kiamat (Yaum al-Qiyāmah)",
        "yaumul qiyamah": "tentang Hari Kiamat",

        "al-qari'ah": "tentang Ketukan Dahsyat (Al-Qāri'ah)",
        "ketukan dahsyat": "tentang Ketukan Dahsyat",

        "yaum al-hisab": "tentang Hari Perhitungan Amal (Yaum al-Ḥisāb)",
        "yaumul hisab": "tentang Hari Perhitungan Amal",
        "perhitungan amal": "tentang Hari Perhitungan Amal",

        "yaum al-mizan": "tentang Hari Penimbangan Amal (Yaum al-Mizan)",
        "yaumul mizan": "tentang Hari Penimbangan Amal",
        "mizan": "tentang Timbangan Amal",

        "jahannam": "tentang Neraka Jahannam",
        "jahim": "tentang Neraka Jahim",
        "huthamah": "tentang Neraka Huthamah",
        "hawiyah": "tentang Neraka Hawiyah",
    }

    query_type = detect_query_type(user_text)
    if query_type == "comparative":
        return "Baik, saya akan jelaskan perbandingan berdasarkan Al-Qur'an.\n\n"
    if query_type == "process":
        return "Baik, saya akan jelaskan urutan/tahapan berdasarkan Al-Qur'an.\n\n"
    if query_type == "general":
        return "Baik, berikut gambaran umum berdasarkan Al-Qur'an.\n\n"

    if query_type == "definition":
        for key in narrations.keys():
            if key in lower:
                return f"Baik, saya akan jelaskan {narrations[key]} berdasarkan Al-Qur'an.\n\n"
        return "Baik, saya akan jelaskan berdasarkan Al-Qur'an.\n\n"

    sorted_keys = sorted(narrations.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in lower:
            return f"Baik, saya akan jelaskan {narrations[key]} berdasarkan Al-Qur'an.\n\n"

    return "Baik, berikut penjelasannya berdasarkan Al-Qur'an.\n\n"
