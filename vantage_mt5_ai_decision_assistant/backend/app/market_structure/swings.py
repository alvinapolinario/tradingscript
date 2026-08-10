"""Swing pivot detection — confirmed only after pivot_right bars have closed."""
from __future__ import annotations

from typing import Any

from app.market_structure.types import Candle


def find_swings(
    candles: list[Candle],
    left: int,
    right: int,
    atr_val: float,
    min_atr: float = 0.3,
) -> list[dict[str, Any]]:
    """Detect swing highs/lows using left/right pivot confirmation (no look-ahead)."""
    swings: list[dict[str, Any]] = []
    for i in range(left, len(candles) - right):
        hi = candles[i].high
        lo = candles[i].low
        is_hi = all(hi >= candles[i - j].high for j in range(1, left + 1)) and all(
            hi >= candles[i + j].high for j in range(1, right + 1)
        )
        is_lo = all(lo <= candles[i - j].low for j in range(1, left + 1)) and all(
            lo <= candles[i + j].low for j in range(1, right + 1)
        )
        if is_hi and hi - lo >= min_atr * atr_val:
            swings.append({"type": "HIGH", "price": hi, "time": candles[i].time, "index": i})
        if is_lo and hi - lo >= min_atr * atr_val:
            swings.append({"type": "LOW", "price": lo, "time": candles[i].time, "index": i})
    return swings
