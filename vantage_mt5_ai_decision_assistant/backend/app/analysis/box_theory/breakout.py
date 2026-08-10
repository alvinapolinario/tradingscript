"""Breakout / breakdown detection."""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig, Candle
from app.analysis.box_theory.utils import body_ratio


@dataclass
class BreakoutEvent:
    direction: str  # UP | DOWN
    price: float
    time: int
    body_ratio: float
    buffer_ok: bool
    wick_only: bool


def detect_breakout(
    box: BoxRange,
    candles: list[Candle],
    cfg: BoxStrategyConfig,
    atr_val: float,
    start_idx: int | None = None,
) -> BreakoutEvent | None:
    """Find first valid breakout after box end on closed bars."""
    buf = cfg.breakout_buffer_atr * atr_val
    idx = start_idx if start_idx is not None else 0
    for c in candles[idx:]:
        if c.time <= box.end_time:
            continue
        br = body_ratio(c)
        if c.close > box.high + buf and br >= cfg.min_breakout_body_ratio:
            return BreakoutEvent(
                direction="UP",
                price=c.close,
                time=c.time,
                body_ratio=br,
                buffer_ok=True,
                wick_only=False,
            )
        if c.high > box.high and c.close <= box.high:
            continue  # wick-only above — not breakout
        if c.close < box.low - buf and br >= cfg.min_breakout_body_ratio:
            return BreakoutEvent(
                direction="DOWN",
                price=c.close,
                time=c.time,
                body_ratio=br,
                buffer_ok=True,
                wick_only=False,
            )
    return None
