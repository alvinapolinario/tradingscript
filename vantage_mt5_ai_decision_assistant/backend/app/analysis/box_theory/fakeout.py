"""False breakout / trap detection."""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.box_theory.types import BoxRange, Candle


@dataclass
class FakeoutEvent:
    trap: str  # BULL_TRAP | BEAR_TRAP
    sweep_price: float
    time: int


def detect_fakeout(box: BoxRange, candles: list[Candle], after_time: int) -> FakeoutEvent | None:
    """Price pierces boundary then closes back inside box."""
    for c in candles:
        if c.time <= after_time:
            continue
        if c.high > box.high and c.close < box.high:
            return FakeoutEvent("BULL_TRAP", c.high, c.time)
        if c.low < box.low and c.close > box.low:
            return FakeoutEvent("BEAR_TRAP", c.low, c.time)
    return None
