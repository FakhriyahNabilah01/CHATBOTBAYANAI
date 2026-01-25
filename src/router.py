# src/router.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Union
import re


@dataclass
class RouteDecision:
    # action: "NEW" | "MORE" | "CONTINUE"
    action: str
    add_k: Optional[int] = None
    focus: Union[None, str, List[str]] = None


def fallback_extract_more_n(text: str) -> int:
    """Ambil angka dari perintah 'tambah 5', 'lanjut 10', '5 lagi', dll."""
    t = (text or "").lower()

    patterns = [
        r"tambah(?:kan)?\s+(\d+)",
        r"lanjut(?:kan)?\s+(\d+)",
        r"(\d+)\s+lagi",
        r"next\s+(\d+)",
    ]
    for p in patterns:
        m = re.search(p, t)
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                pass
    return 5


class _RouterChain:
    def invoke(self, inputs: dict) -> RouteDecision:
        text = (inputs.get("text") or "").strip().lower()

        # detect focus
        focus = None
        if "hamka" in text:
            focus = ["hamka"]
        elif "wajiz" in text:
            focus = ["kemenag_wajiz"]
        elif "tahlili" in text:
            focus = ["kemenag_tahlili"]

        # detect action MORE
        if any(k in text for k in ["tambah", "lagi", "next", "berikan lagi", "lanjut 5", "lanjutkan 5"]):
            return RouteDecision(action="MORE", add_k=fallback_extract_more_n(text), focus=focus)

        # detect CONTINUE (lanjutkan tanpa tambah jumlah)
        if any(k in text for k in ["lanjutkan", "lanjut", "continue", "teruskan"]):
            return RouteDecision(action="CONTINUE", add_k=None, focus=focus)

        # default: NEW query
        return RouteDecision(action="NEW", add_k=None, focus=focus)


router_chain = _RouterChain()
