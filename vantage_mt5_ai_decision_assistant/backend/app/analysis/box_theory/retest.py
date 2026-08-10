"""Retest detection after breakout."""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.box_theory.breakout import BreakoutEvent
from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig, Candle
from app.analysis.box_theory.utils import body_ratio, is_bearish, is_bullish


@dataclass
class RetestEvent:
    detected: bool
    confirmed: bool
    price: float
    time: int
    candles_waited: int


def detect_retest(
    box: BoxRange,
    breakout: BreakoutEvent,
    candles: list[Candle],
    cfg: BoxStrategyConfig,
    atr_val: float,
) -> RetestEvent:
    tol = cfg.retest_tolerance_atr * atr_val
    after = [c for c in candles if c.time > breakout.time][: cfg.max_retest_candles]
    if not after:
        return RetestEvent(False, False, 0.0, 0, 0)

    for i, c in enumerate(after, 1):
        if breakout.direction == "UP":
            near = abs(c.low - box.high) <= tol or (box.high - tol <= c.close <= box.high + tol)
            if not near:
                continue
            confirmed = is_bullish(c) and c.close >= box.high - tol * 0.5
            if confirmed or i >= cfg.confirmation_candles:
                return RetestEvent(True, confirmed, c.close, c.time, i)
        else:
            near = abs(c.high - box.low) <= tol or (box.low - tol <= c.close <= box.low + tol)
            if not near:
                continue
            confirmed = is_bearish(c) and c.close <= box.low + tol * 0.5
            if confirmed or i >= cfg.confirmation_candles:
                return RetestEvent(True, confirmed, c.close, c.time, i)
    return RetestEvent(False, False, 0.0, 0, len(after))
