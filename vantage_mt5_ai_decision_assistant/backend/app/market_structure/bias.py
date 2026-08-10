"""Higher-timeframe bias from closed candle closes."""
from __future__ import annotations

from app.market_structure.types import Candle


def htf_bias(candles: list[Candle], lookback: int = 20, threshold_pct: float = 0.002) -> str:
    """Simple HTF bias: compare first vs last close over lookback window."""
    if len(candles) < lookback:
        return "NEUTRAL"
    closes = [c.close for c in candles[-lookback:]]
    if closes[-1] > closes[0] * (1.0 + threshold_pct):
        return "BULLISH"
    if closes[-1] < closes[0] * (1.0 - threshold_pct):
        return "BEARISH"
    return "NEUTRAL"
