"""Default per-strategy confluence weights."""
from __future__ import annotations

DEFAULT_STRATEGY_WEIGHTS: dict[str, float] = {
    "ICT": 1.0,
    "AMD_IFVG": 0.95,
    "BOX_THEORY": 0.9,
    "GOLD_SMC": 0.9,
    "SWING": 1.0,
    "LIQUIDITY_GRAB": 0.85,
    "BREAKOUT": 0.8,
    "M30_CORE": 0.75,
}

__all__ = ["DEFAULT_STRATEGY_WEIGHTS"]
