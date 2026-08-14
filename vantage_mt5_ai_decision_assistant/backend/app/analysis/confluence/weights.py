"""Default per-strategy confluence weights."""
from __future__ import annotations

DEFAULT_STRATEGY_WEIGHTS: dict[str, float] = {
    "ICT": 1.0,
    "AMD_IFVG": 0.95,
    "BOX_THEORY": 0.9,
    "GOLD_SMC": 0.9,
    "SWING": 1.0,
    "LIQUIDITY_GRAB": 0.85,
    "H4_M15_FVG": 0.88,
    "BREAKOUT": 0.8,
    "M30_CORE": 0.75,
    "MACRO": 0.35,
}

__all__ = ["DEFAULT_STRATEGY_WEIGHTS"]
