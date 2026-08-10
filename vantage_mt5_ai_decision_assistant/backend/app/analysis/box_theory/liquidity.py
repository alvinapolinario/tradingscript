"""Liquidity sweep confirmation around box."""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig, Candle


@dataclass
class LiquiditySweep:
    detected: bool
    direction: str  # SELL_SIDE | BUY_SIDE
    sweep_price: float
    sweep_time: int
    level: float


def detect_liquidity_sweep(
    box: BoxRange,
    candles: list[Candle],
    cfg: BoxStrategyConfig,
    atr_val: float,
    before_time: int,
) -> LiquiditySweep:
    if not cfg.liquidity_sweep_detection:
        return LiquiditySweep(False, "", 0.0, 0, 0.0)
    tol = cfg.breakout_buffer_atr * atr_val
    relevant = [c for c in candles if box.start_time <= c.time <= before_time]
    for c in reversed(relevant):
        if c.low < box.low - tol and c.close > box.low:
            return LiquiditySweep(True, "SELL_SIDE", c.low, c.time, box.low)
        if c.high > box.high + tol and c.close < box.high:
            return LiquiditySweep(True, "BUY_SIDE", c.high, c.time, box.high)
    return LiquiditySweep(False, "", 0.0, 0, 0.0)
