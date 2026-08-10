"""Confluence engine — shared types."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Direction = Literal["LONG", "SHORT", "NEUTRAL", "NO_SETUP"]


@dataclass
class StrategySignal:
    strategy: str
    direction: Direction
    confidence: float
    status: str
    evidence: list[str] = field(default_factory=list)
    invalidation: list[str] = field(default_factory=list)
    timestamp: int = 0
    freshness_sec: float = 0.0
    weight: float = 1.0
    active: bool = True


@dataclass
class ConfluenceConfig:
    enabled: bool = False
    freshness_threshold_sec: float = 900.0
    stale_weight_factor: float = 0.5
    min_agreeing_for_strong: int = 2
    min_confidence_strong: float = 78.0
    min_confidence_setup: float = 62.0
    conflict_penalty: float = 18.0
    neutral_threshold: float = 8.0
    strategy_weights: dict[str, float] = field(default_factory=dict)


@dataclass
class ConfluenceResult:
    overall_direction: Direction
    confidence: float
    agreement: str
    agreeing_count: int
    active_count: int
    conflicting_strategies: list[str]
    strongest_strategy: str
    components: dict[str, dict]
    summary: str
    score_long: float = 0.0
    score_short: float = 0.0

    def to_dict(self) -> dict:
        return {
            "overall_direction": self.overall_direction,
            "confidence": round(self.confidence, 1),
            "agreement": self.agreement,
            "agreeing_count": self.agreeing_count,
            "active_count": self.active_count,
            "conflicting_strategies": self.conflicting_strategies,
            "strongest_strategy": self.strongest_strategy,
            "components": self.components,
            "summary": self.summary,
            "score_long": round(self.score_long, 2),
            "score_short": round(self.score_short, 2),
        }
