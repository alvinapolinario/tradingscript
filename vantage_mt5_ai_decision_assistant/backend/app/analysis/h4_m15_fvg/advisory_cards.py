"""Read-only Signal Center advisory cards from H4→M15 FVG monitor state."""
from __future__ import annotations

from typing import Any


def _side_from_direction(direction: str) -> str:
    d = (direction or "").upper()
    if d in ("BULLISH", "LONG", "BUY"):
        return "BUY"
    if d in ("BEARISH", "SHORT", "SELL"):
        return "SELL"
    return ""


def build_h4_m15_advisory_cards(ea: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Build advisory cards when the selected symbol has ENTRY_READY H4→M15 setup."""
    if not isinstance(ea, dict):
        return []

    blob = ea.get("h4_m15_fvg")
    if not isinstance(blob, dict) or not blob.get("valid"):
        return []

    primary = blob.get("primary")
    if not isinstance(primary, dict):
        return []

    state = str(primary.get("state") or "").upper()
    decision = str(primary.get("decision") or "").upper()
    if state != "ENTRY_READY" and decision != "ENTRY_READY":
        return []

    side = _side_from_direction(str(primary.get("direction") or ""))
    if not side:
        return []

    entry_fvg = primary.get("entry_fvg") if isinstance(primary.get("entry_fvg"), dict) else {}
    entry_low = float(entry_fvg.get("lower") or 0.0)
    entry_high = float(entry_fvg.get("upper") or 0.0)
    if entry_low <= 0 or entry_high <= 0:
        entry_price = float(primary.get("entry_price") or 0.0)
        if entry_price > 0:
            entry_low = entry_high = entry_price

    liquidity = primary.get("liquidity") if isinstance(primary.get("liquidity"), dict) else {}
    structure = primary.get("structure") if isinstance(primary.get("structure"), dict) else {}

    return [
        {
            "source": "H4_M15_FVG",
            "kind": "advisory",
            "advisory_only": True,
            "symbol": str(primary.get("symbol") or ea.get("symbol") or "—"),
            "side": side,
            "timeframe": "H4→M15",
            "mode": "H4_M15_FVG",
            "state": state or decision,
            "decision": decision or state,
            "score": primary.get("score"),
            "grade": primary.get("grade"),
            "setup_id": primary.get("setup_id"),
            "entry_low": entry_low,
            "entry_high": entry_high,
            "entry_price": primary.get("entry_price"),
            "stop": primary.get("structural_stop"),
            "target": None,
            "entry_ready_time": primary.get("entry_ready_time"),
            "sweep_detected": bool(liquidity.get("sweep_detected")),
            "mss_confirmed": bool(structure.get("mss_confirmed")),
            "desk_path": "/h4-m15-fvg",
            "summary": f"H4→M15 FVG {side} — ENTRY_READY (analysis only)",
        }
    ]
