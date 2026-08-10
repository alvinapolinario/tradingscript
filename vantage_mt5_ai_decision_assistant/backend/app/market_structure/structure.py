"""Market structure shift detection (MSS)."""
from __future__ import annotations

from typing import Any, Protocol

from app.market_structure.types import Candle


class MssSettings(Protocol):
    displacement_min_body_atr: float


def detect_mss(
    candles: list[Candle],
    swings: list[dict[str, Any]],
    bias: str,
    atr: float,
    cfg: MssSettings,
) -> dict[str, Any] | None:
    if len(candles) < 3:
        return None
    last = candles[-1]
    body = abs(last.close - last.open)
    if body / atr < cfg.displacement_min_body_atr * 0.5:
        return None
    body_lo = min(last.open, last.close)
    body_hi = max(last.open, last.close)
    if bias == "BEARISH":
        lows = [s for s in swings if s["type"] == "LOW"]
        if not lows:
            return None
        level = lows[-1]["price"]
        if body_lo < level:
            return {
                "shift_detected": True,
                "direction": "BEARISH",
                "broken_level": level,
                "confirmation_type": "BODY_CLOSE",
                "quality_score": min(100.0, 60.0 + body / atr * 25.0),
            }
    if bias == "BULLISH":
        highs = [s for s in swings if s["type"] == "HIGH"]
        if not highs:
            return None
        level = highs[-1]["price"]
        if body_hi > level:
            return {
                "shift_detected": True,
                "direction": "BULLISH",
                "broken_level": level,
                "confirmation_type": "BODY_CLOSE",
                "quality_score": min(100.0, 60.0 + body / atr * 25.0),
            }
    return None
