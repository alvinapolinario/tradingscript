"""Shared market-structure types — used by AMD, Box Theory, ICT, and future strategies."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class FvgDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FvgStatus(str, Enum):
    FRESH = "FRESH"
    ACTIVE = "ACTIVE"  # backward-compatible alias for FRESH
    TOUCHED = "TOUCHED"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
    MIDPOINT_REACHED = "MIDPOINT_REACHED"
    FULLY_MITIGATED = "FULLY_MITIGATED"
    INVALIDATED = "INVALIDATED"
    INVERTED = "INVERTED"
    EXPIRED = "EXPIRED"


@dataclass
class FvgZone:
    fvg_id: str
    direction: str  # BULLISH | BEARISH
    timeframe: str
    created_time: int
    lower: float
    upper: float
    gap_size: float
    gap_atr: float
    displacement_score: float
    mitigation_pct: float = 0.0
    status: FvgStatus = FvgStatus.FRESH
    inverted: bool = False
    inversion_time: int = 0
    retest_count: int = 0
    original_direction: str = ""
    symbol: str = ""
    candle1_time: int = 0
    candle2_time: int = 0
    candle3_time: int = 0
    atr: float = 0.0
    first_touch_time: int = 0
    midpoint_touch_time: int = 0
    full_fill_time: int = 0
    invalidated_time: int = 0
    parent_fvg_id: str = ""
    created_at: int = 0
    updated_at: int = 0

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0

    @property
    def normalized_gap_size(self) -> float:
        return self.gap_atr
