"""Configurable FVG entry interaction — TOUCH, closed bar, or CE."""
from __future__ import annotations

from app.analysis.ict.types import EntryTriggerMode
from app.market_structure.types import Candle, FvgZone


def fvg_interaction_met(
    fvg: FvgZone,
    *,
    price: float,
    last_exec_candle: Candle | None,
    mode: EntryTriggerMode,
    atr_exec: float,
) -> tuple[bool, str]:
    """Return (interaction_met, interaction_kind)."""
    low, high = fvg.lower, fvg.upper
    if high <= low:
        return False, ""

    mid = fvg.midpoint
    tol = max(1e-9, atr_exec * 0.05)

    if mode == EntryTriggerMode.CE_TOUCH:
        if abs(price - mid) <= tol:
            return True, "CE_TOUCH"
        if low <= price <= high and (
            (fvg.direction == "BULLISH" and price <= mid + tol)
            or (fvg.direction == "BEARISH" and price >= mid - tol)
        ):
            return True, "CE_TOUCH"
        return False, ""

    if mode == EntryTriggerMode.CLOSED_BAR_TOUCH:
        c = last_exec_candle
        if not c:
            return False, ""
        body_lo = min(c.open, c.close)
        body_hi = max(c.open, c.close)
        overlaps = not (body_hi < low or body_lo > high)
        wick_overlaps = c.high >= low and c.low <= high
        if overlaps or wick_overlaps:
            return True, "CLOSED_BAR_TOUCH"
        return False, ""

    # TOUCH — live bid/ask or last close
    if low <= price <= high:
        return True, "TOUCH"
    return False, ""
