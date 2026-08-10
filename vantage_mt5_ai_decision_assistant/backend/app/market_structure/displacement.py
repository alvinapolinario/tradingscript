"""Displacement scoring — objective multi-factor candle strength."""
from __future__ import annotations

from app.market_structure.types import Candle


def score_displacement(candle: Candle, atr: float, structure_break: bool, fvg_created: bool) -> float:
    body = abs(candle.close - candle.open)
    rng = candle.high - candle.low or 1e-9
    score = 0.0
    score += min(25.0, (body / atr) * 25.0) if atr else 0.0
    score += min(15.0, (body / rng) * 15.0)
    if structure_break:
        score += 25.0
    if fvg_created:
        score += 15.0
    if candle.close > candle.open and candle.close >= candle.high - rng * 0.25:
        score += 10.0
    if candle.close < candle.open and candle.close <= candle.low + rng * 0.25:
        score += 10.0
    return min(100.0, score)
