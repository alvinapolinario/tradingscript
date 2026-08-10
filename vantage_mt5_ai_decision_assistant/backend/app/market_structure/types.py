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


class FvgStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PARTIALLY_MITIGATED = "PARTIALLY_MITIGATED"
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
    status: FvgStatus = FvgStatus.ACTIVE
    inverted: bool = False
    inversion_time: int = 0
    retest_count: int = 0
    original_direction: str = ""

    @property
    def midpoint(self) -> float:
        return (self.lower + self.upper) / 2.0
