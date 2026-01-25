# src/chatbot.py
from __future__ import annotations

from typing import Dict, Any, List, Optional

from state import get_state

from query_utils import (
    enrich_topic_with_terminology,
    enrich_topic_with_category,
    generate_opening_narration,
    get_smart_search_limit,
    get_smart_ayat_count,
)

from embeddings import embed_query
from neo4j_client import graphrag_search
from search_flow import format_many

# router_chain, RouteDecision, fallback_extract_more_n:
from router import router_chain, RouteDecision, fallback_extract_more_n


def _ensure_state_defaults(state: Dict[str, Any]) -> None:
    """Pastikan key penting di state selalu ada."""
    defaults = {
        "history": [],
        "last_query_text": None,
        "last_query_embedding": None,
        "last_results": [],
        "shown": 0,
        "page_size": 5,
        "last_limit": 5,
        "last_focus": [],
        "active_topic": None,
        "score_threshold": 0.70,  # dipakai graphrag_search
    }
    for k, v in defaults.items():
        state.setdefault(k, v)


def deduplicate_ayat(ayat_list: List[Dict[str, Any]], debug_label: str = "") -> List[Dict[str, Any]]:
    """
    Deduplikasi ayat berdasarkan identifier unik.
    Prioritas: ayat_id / IdAyat → (nama_surat.upper(), ayat_ke)
    """
    unique: List[Dict[str, Any]] = []
    seen = set()
    duplicates_found = 0

    for rec in ayat_list or []:
        ayat_id = rec.get("ayat_id") or rec.get("IdAyat")
        if ayat_id is not None:
            key = f"ID:{ayat_id}"
        else:
            surat = str(rec.get("nama_surat", "UNKNOWN")).strip().upper()
            ayat_ke = rec.get("ayat_ke", 0)
            key = (surat, ayat_ke)

        if key not in seen:
            seen.add(key)
            unique.append(rec)
        else:
            duplicates_found += 1
            if debug_label:
                print(f"[DUPLIKAT {debug_label}] {key} → dilewati")

    if debug_label:
        print(f"[DEDUP {debug_label}] input={len(ayat_list)} unik={len(unique)} duplikat={duplicates_found}")

    return unique


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Biar aman kalau field di RouteDecision beda-beda."""
    return getattr(obj, name, default)


def run_chatbot(user_text: str, session_id: str = "default") -> str:
    user_text = (user_text or "").strip()
    if not user_text:
        return "Pertanyaan kosong."

    state = get_state(session_id)
    _ensure_state_defaults(state)

    # =========================
    # 0) Enrich topic (untuk query baru)
    # =========================
    enriched_topic = enrich_topic_with_terminology(user_text, user_text)
    enriched_topic = enrich_topic_with_category(user_text, enriched_topic)

    # =========================
    # 1) Routing (NEW / MORE / CONTINUE / (opsional) DETAIL / CLARIFY)
    # =========================
    try:
        decision: RouteDecision = router_chain.invoke({"text": user_text})
    except Exception as e:
        # fallback kalau router error: treat sebagai query baru
        print(f"[WARN] router_chain gagal: {e} → fallback NEW")
        decision = RouteDecision(action="NEW", add_k=0, focus=[])

    action = _safe_getattr(decision, "action", "NEW")

    # fallback jumlah "tambah N" kalau router gak ngisi add_k
    add_k = _safe_getattr(decision, "add_k", 0)
    if action == "MORE" and (add_k is None or add_k == 0):
        add_k = fallback_extract_more_n(user_text) or 0

    decision_focus = _safe_getattr(decision, "focus", []) or []
    focus = (
        decision_focus
        if action not in ("MORE", "CONTINUE")
        else (decision_focus or state["last_focus"])
    )

    # ======================
    # 2) QUERY BARU
    # ======================
    if action == "NEW" or state["last_query_embedding"] is None:
        # smart limit: pertanyaan "beda/vs/semua" bisa naik limit otomatis
        limit = get_smart_search_limit(user_text, default=int(state["last_limit"] or state["page_size"]))

        vec = embed_query(enriched_topic)
        results = graphrag_search(
            vec,
            limit=limit,
            score_threshold=float(state["score_threshold"]),
        )
        results = deduplicate_ayat(results, debug_label="NEW")

        # smart jumlah ayat yang ditampilkan awal
        shown = min(
            get_smart_ayat_count(user_text, available=len(results), default=int(state["page_size"])),
            len(results),
        )

        state["last_query_embedding"] = vec
        state["last_query_text"] = enriched_topic
        state["last_results"] = results
        state["shown"] = shown
        state["last_limit"] = limit
        state["last_focus"] = focus
        state["active_topic"] = enriched_topic

        if not results:
            return "Tidak ada hasil yang cocok."

        return format_many(results[:shown], focus=focus)

    # ======================
    # 3) TAMBAH HASIL (MORE)
    # ======================
    if action == "MORE":
        # kalau user bilang "tambah 10", tampilkan 10 (bukan cuma page_size)
        step = int(add_k) if add_k else int(state["page_size"])
        state["last_limit"] = int(state["last_limit"]) + step

        results = graphrag_search(
            state["last_query_embedding"],
            limit=int(state["last_limit"]),
            score_threshold=float(state["score_threshold"]),
        )
        results = deduplicate_ayat(results, debug_label="MORE")

        old_shown = int(state["shown"])
        new_shown = min(len(results), old_shown + step)

        tambahan = results[old_shown:new_shown]

        state["last_results"] = results
        state["shown"] = new_shown
        state["last_focus"] = focus

        return (
            format_many(tambahan, focus=focus)
            if tambahan
            else "Tidak ada tambahan hasil yang relevan."
        )

    # ======================
    # 4) CONTINUE
    # ======================
    if action == "CONTINUE":
        if not state["last_results"]:
            return "❌ Belum ada konteks sebelumnya. Tanyakan topik dulu ya."

        state["last_focus"] = focus
        narration = generate_opening_narration(
            "continue",
            state["active_topic"] or state["last_query_text"] or "",
            user_text,
        )
        return narration + format_many(
            state["last_results"][: int(state["shown"])],
            focus=focus,
        )

    # ======================
    # 5) OPSIONAL: DETAIL (kalau router kamu support)
    # ======================
    if action == "DETAIL":
        if not state["last_results"]:
            return "❌ Belum ada hasil sebelumnya untuk dilihat detailnya."

        ayat_number = _safe_getattr(decision, "ayat_number", None)
        if ayat_number is None:
            return "❌ Sebutkan nomor ayat hasil yang mau dijelaskan (contoh: 'jelaskan ayat 2')."

        idx = int(ayat_number) - 1
        if idx < 0 or idx >= len(state["last_results"]):
            return f"❌ Nomor ayat tidak valid. Pilih 1 sampai {len(state['last_results'])}."

        return format_many([state["last_results"][idx]], focus=focus)

    # ======================
    # 6) OPSIONAL: CLARIFY (kalau router kamu support)
    # ======================
    if action == "CLARIFY":
        msg = _safe_getattr(decision, "clarify_message", None)
        return msg or "❓ Bisa diperjelas maksudnya? (misal: topik apa, mau tafsir siapa, dan berapa ayat)"

    return "❌ Terjadi error pada routing."
