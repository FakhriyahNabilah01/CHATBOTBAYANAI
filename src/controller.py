import re
from typing import List, Dict, Any, Optional, Set

from src.state import get_state
from src.embeddings import embed_query
from src.neo4j_client import graphrag_search, run_cypher  # pastikan run_cypher ada
from langchain_openai import ChatOpenAI


# =========================
# Utils parsing command
# =========================
def is_lanjut_cmd(text: str) -> bool:
    t = (text or "").strip().lower()
    return t.startswith("lanjut") or t in {"lanjut", "next", "lebih", "tambah"}

def extract_number_natural(text: str) -> Optional[int]:
    text = (text or "").lower().strip()

    # angka digit
    m = re.search(r"\b(\d{1,4})\b", text)
    if m:
        return int(m.group(1))

    # angka kata sederhana
    words = {
        "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
        "enam": 6, "tujuh": 7, "delapan": 8, "sembilan": 9, "sepuluh": 10
    }
    for k, v in words.items():
        if re.search(rf"\b{k}\b", text):
            return v
    return None

def detect_sources(text: str) -> Set[str]:
    text = (text or "").lower()
    sources = set()
    if any(k in text for k in ["tahlili", "kemenag tahlili", "tafsir tahlili"]):
        sources.add("tahlili")
    if any(k in text for k in ["wajiz", "kemenag wajiz", "tafsir wajiz"]):
        sources.add("wajiz")
    if any(k in text for k in ["hamka", "buya hamka", "tafsir hamka"]):
        sources.add("hamka")
    if any(k in text for k in ["semua", "lengkap", "full", "all"]):
        sources.add("all")
    return sources if sources else {"all"}


# =========================
# Normalisasi record keys
# =========================
def _normalize_record_keys(r: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(r or {})

    # ayat number
    if "ayat_ke" not in out and "ayat" in out:
        out["ayat_ke"] = out.get("ayat")

    # arab
    if "arab_ayat" not in out and "ayat_arab" in out:
        out["arab_ayat"] = out.get("ayat_arab")

    # tafsir naming variants dari neo4j_client.py kamu
    if "tafsir_hamka" not in out and "tafsir_buya_hamka" in out:
        out["tafsir_hamka"] = out.get("tafsir_buya_hamka")

    if "tafsir_tahlili" not in out and "tafsir_kemenag_tahlili" in out:
        out["tafsir_tahlili"] = out.get("tafsir_kemenag_tahlili")

    if "tafsir_wajiz" not in out and "tafsir_kemenag_wajiz" in out:
        out["tafsir_wajiz"] = out.get("tafsir_kemenag_wajiz")

    # kategori list
    kat = out.get("kategori")
    if kat is None:
        out["kategori"] = []
    elif isinstance(kat, str):
        out["kategori"] = [kat]
    elif not isinstance(kat, list):
        out["kategori"] = list(kat)

    return out


# =========================
# Format output ayat
# =========================
def format_ayat_record(r0: Dict[str, Any], sources: Set[str]) -> str:
    r = _normalize_record_keys(r0)

    lines = [
        f"**Ayat {r.get('ayat_ke', '?')} – {r.get('nama_surat', '?')}**",
        (r.get("arab_ayat") or "").strip(),
        f"**Artinya:** {(r.get('terjemahan') or '').strip() or 'Tidak tersedia'}",
    ]

    kategori = [k.strip() for k in (r.get("kategori") or []) if k and str(k).strip()]
    if kategori:
        lines.append(f"**Kategori:** {', '.join(kategori)}")

    if ("all" in sources or "tahlili" in sources) and r.get("tafsir_tahlili"):
        lines.append("\n**Tafsir Kemenag (Tahlili):**")
        lines.append(str(r["tafsir_tahlili"]).strip())

    if ("all" in sources or "wajiz" in sources) and r.get("tafsir_wajiz"):
        lines.append("\n**Tafsir Kemenag (Wajiz):**")
        lines.append(str(r["tafsir_wajiz"]).strip())

    if ("all" in sources or "hamka" in sources) and r.get("tafsir_hamka"):
        lines.append("\n**Tafsir Buya Hamka:**")
        lines.append(str(r["tafsir_hamka"]).strip())

    return "\n".join([x for x in lines if x is not None and x != ""])


# =========================
# Dedup
# =========================
def _dedup_by_surat_ayat(rows: List[Dict[str, Any]], label: str = "") -> List[Dict[str, Any]]:
    seen = set()
    out = []
    dup = 0
    for r0 in rows:
        r = _normalize_record_keys(r0)
        key = (str(r.get("nama_surat", "")).strip().upper(), int(r.get("ayat_ke") or 0))
        if key not in seen:
            seen.add(key)
            out.append(r)
        else:
            dup += 1
    if label:
        print(f"[DEDUP {label}] input={len(rows)} unik={len(out)} duplikat={dup}")
    return out


# =========================
# Manual search by category
# =========================
def manual_category_search(cid: int) -> List[Dict[str, Any]]:
    # NOTE: ini sudah versi aman (no DISTINCT akses a di ORDER BY)
    cypher = """
    MATCH (a:Ayat)-[:`masuk Ke`|masuk_ke]->(k:Kategori {IdKategori: $cid})
    OPTIONAL MATCH (s:Surat)-[:beradadi|terdapat]-(a)
    OPTIONAL MATCH (a)-[:memiliki_arti|untuk]-(tr:Terjemahan)
    OPTIONAL MATCH (a)-[:pada|masuk_ke]-(k2:Kategori)
    OPTIONAL MATCH (a)-[:terdapat|memiliki]-(th:TafsirKemenagTahlili)
    OPTIONAL MATCH (a)-[:terdapat|memiliki]-(wz:TafsirKemenagWajiz)
    OPTIONAL MATCH (a)-[:terdapat|memiliki]-(bh:TafsirBuyaHamka)

    WITH
      s.Surat AS nama_surat,
      toInteger(a.AyatKe) AS ayat_ke,
      a.Ayat AS arab_ayat,
      head(collect(DISTINCT tr.Terjemahan)) AS terjemahan,
      collect(DISTINCT k2.Kategori) AS kategori,
      head(collect(DISTINCT th.TafsirKemenagTahlili)) AS tafsir_tahlili,
      head(collect(DISTINCT wz.TafsirKemenagWajiz)) AS tafsir_wajiz,
      head(collect(DISTINCT bh.TafsirBuyaHamka)) AS tafsir_hamka

    RETURN
      nama_surat, ayat_ke, arab_ayat, terjemahan, kategori,
      tafsir_tahlili, tafsir_wajiz, tafsir_hamka,
      3.0 AS score
    ORDER BY nama_surat ASC, ayat_ke ASC
    """
    return run_cypher(cypher, cid=cid)


# =========================
# Kesimpulan panjang (bisa pakai yang aku kasih sebelumnya)
# =========================
_CONCLUSION_LLM = None
def _get_llm():
    global _CONCLUSION_LLM
    if _CONCLUSION_LLM is None:
        _CONCLUSION_LLM = ChatOpenAI(model="gpt-4o", temperature=0)
    return _CONCLUSION_LLM

def generate_contextual_conclusion(topic: str, records: List[Dict[str, Any]], sources: Set[str], is_final: bool = False) -> str:
    if not records:
        return "Belum ada data untuk kesimpulan."

    # ambil bahan
    max_records = 12 if not is_final else 30
    chunks = []
    for r0 in records[:max_records]:
        r = _normalize_record_keys(r0)
        if r.get("terjemahan"):
            chunks.append(f"- TERJ: {r['terjemahan']}")
        if ("all" in sources or "tahlili" in sources) and r.get("tafsir_tahlili"):
            chunks.append(f"- TAHLILI: {r['tafsir_tahlili']}")
        if ("all" in sources or "wajiz" in sources) and r.get("tafsir_wajiz"):
            chunks.append(f"- WAJIZ: {r['tafsir_wajiz']}")
        if ("all" in sources or "hamka" in sources) and r.get("tafsir_hamka"):
            chunks.append(f"- HAMKA: {r['tafsir_hamka']}")

    if not chunks:
        return "Tidak cukup data tafsir/terjemahan untuk menyusun kesimpulan."

    prompt = f"""
Berdasarkan potongan terjemahan & tafsir berikut tentang "{topic}":
{chr(10).join(chunks)}

Tulis kesimpulan yang BENAR-BENAR merangkum isi ayat yang ditampilkan.
- 2 paragraf, total 8–12 kalimat.
- Paragraf 1: benang merah tema & makna utama.
- Paragraf 2: implikasi perilaku manusia di dunia (tetap berbasis teks).
- Hindari pengulangan.
- Bahasa Indonesia formal dan jelas.
""".strip()

    try:
        llm = _get_llm()
        resp = llm.invoke(prompt)
        return (resp.content or "").strip() or "Kesimpulan gagal dibuat."
    except Exception as e:
        print(f"[ERROR] Kesimpulan gagal: {e}")
        return "Kesimpulan gagal dibuat karena error teknis."


# =========================
# CONTROLLER (return full text)
# =========================
def controller(user_text: str, session_id: str = "default") -> str:
    user_text = (user_text or "").strip()
    if not user_text:
        return "Masukkan pertanyaan atau perintah."

    state = get_state(session_id)
    state.setdefault("last_results", [])
    state.setdefault("cursor", 0)
    state.setdefault("page_size", 5)
    state.setdefault("active_topic", None)

    sources = detect_sources(user_text)
    lower = user_text.lower()
    is_lanjut = is_lanjut_cmd(user_text)

    out: List[str] = []

    # ---------------------------
    # MODE QUERY BARU
    # ---------------------------
    if not is_lanjut:
        state["last_results"] = []
        state["cursor"] = 0
        state["active_topic"] = user_text

        out.append("[DEBUG] === RESET TOTAL STATE UNTUK QUERY BARU ===")
        out.append(f"[DEBUG] Topic setelah enrich: {user_text}")

        # ambil angka kalau user bilang "3 ..."
        n_req = extract_number_natural(user_text)
        if n_req is not None and n_req > 0:
            page_size = n_req
        else:
            page_size = int(state.get("page_size", 5))
        if page_size <= 0:
            page_size = 5
        state["page_size"] = page_size  # simpan

        # DETECT CATEGORY
        category_keywords = {
            "yaum al-mizan": ["mizan", "yaumul mizan", "yaum al-mizan", "timbangan", "penimbangan", "ثقلت", "خفت"],
            "yaum al-hisab": ["hisab", "yaumul hisab", "yaum al-hisab", "perhitungan amal", "حساب"],
        }

        best = None
        max_score = 0
        for cat, kws in category_keywords.items():
            score = sum(1 for kw in kws if kw in lower)
            if score > max_score:
                max_score = score
                best = cat

        detected_categories = [best] if best else []
        out.append(f"[DEBUG] Detected categories: {detected_categories}, score: {max_score}")

        category_id_map = {"yaum al-hisab": 12, "yaum al-mizan": 13}

        # MANUAL
        manual_results: List[Dict[str, Any]] = []
        for cat in detected_categories:
            cid = category_id_map.get(cat)
            if cid is None:
                continue
            rows = manual_category_search(cid)
            manual_results.extend(rows)
            out.append(f"[✅ MANUAL] Ditemukan {len(rows)} ayat dari '{cat}' (ID {cid})")

        manual_results = _dedup_by_surat_ayat(manual_results, label="MANUAL")
        if manual_results:
            out.append(f"[DEBUG] Total manual setelah dedup multi: {len(manual_results)} ayat")

        # VECTOR
        vec = embed_query(user_text)
        vector_results = graphrag_search(vec, limit=50, score_threshold=0.72)

        filtered_vector: List[Dict[str, Any]] = []
        for r0 in vector_results:
            r = _normalize_record_keys(r0)
            text_all = (
                (r.get("terjemahan") or "")
                + (r.get("tafsir_tahlili") or "")
                + (r.get("tafsir_wajiz") or "")
                + (r.get("tafsir_hamka") or "")
            ).lower()

            if "dunia" in lower or "di dunia" in lower:
                if "kiamat" in text_all or "akhirat" in text_all:
                    if not any(kw in text_all for kw in ["dunia", "dilarang", "maksiat", "tamak", "kikir", "ghibah"]):
                        continue
            filtered_vector.append(r)

        out.append(f"[DEBUG] Vector setelah filter: {len(filtered_vector)} ayat")

        # GABUNG + SORT
        all_results = manual_results + filtered_vector
        all_results = _dedup_by_surat_ayat(all_results, label="ALL")
        all_results.sort(key=lambda x: (-float(x.get("score", 0)), str(x.get("nama_surat", "")), int(x.get("ayat_ke", 0))))

        state["last_results"] = all_results
        out.append(f"[DEBUG] Total ayat unik: {len(all_results)}")
        out.append(f"Berikut ayat-ayat terkait '{user_text}' beserta terjemahan dan tafsir yang tersedia:\n")

        # BATCH sesuai page_size / angka request
        batch = all_results[:page_size]
        state["cursor"] = len(batch)

        if not batch:
            # kalau kosong, jelaskan biar tidak “silent”
            out.append("Tidak ada ayat yang bisa ditampilkan pada batch pertama (batch kosong).")
            out.append("Cek: page_size, hasil query Neo4j, atau mapping key record.")
            out.append("\nOutput selesai (cek tampilan di atas).")
            return "\n".join(out)

        for r in batch:
            out.append(format_ayat_record(r, sources))
            out.append("\n" + ("═" * 60) + "\n")

        concl = generate_contextual_conclusion(user_text, batch, sources, is_final=False)
        out.append(f"📌 **Kesimpulan:**\n{concl}\n")

        remaining = len(all_results) - state["cursor"]
        if remaining > 0:
            out.append(f"📝 Ketik **lanjut** untuk lihat sisa {remaining} ayat.")

        out.append("Output selesai (cek tampilan di atas).")
        return "\n".join(out)

    # ---------------------------
    # MODE LANJUT
    # ---------------------------
    if not state.get("last_results"):
        return "❌ Tidak ada hasil sebelumnya. Silakan ajukan pertanyaan baru."

    cursor = int(state.get("cursor", 0))
    total = len(state["last_results"])
    remaining = total - cursor
    if remaining <= 0:
        return "✅ Semua ayat sudah ditampilkan."

    n_req = extract_number_natural(user_text)
    if n_req is not None and n_req > 0:
        n = min(n_req, remaining)
    else:
        n = remaining

    start = cursor
    end = start + n
    batch = state["last_results"][start:end]
    state["cursor"] = end

    out.append("Melanjutkan hasil sebelumnya...\n")
    for r in batch:
        out.append(format_ayat_record(r, sources))
        out.append("\n" + ("═" * 60) + "\n")

    remaining_now = total - end
    if remaining_now <= 0:
        concl = generate_contextual_conclusion(state["active_topic"], state["last_results"], sources, is_final=True)
        out.append(f"\n📌 **Kesimpulan Akhir:**\n{concl}\n✅ Semua ayat telah ditampilkan.")
    else:
        concl = generate_contextual_conclusion(state["active_topic"], batch, sources, is_final=False)
        out.append(f"\n📌 **Kesimpulan Sementara:**\n{concl}\n")
        out.append(f"📝 Masih ada {remaining_now} ayat. Ketik **lanjut** atau **lanjut [angka]** (misal: lanjut 5).")

    return "\n".join(out)
