"""ICT event identity helpers."""
from __future__ import annotations

from app.analysis.ict.types import LiquidityLevel, LiquiditySweepEvent


def liquidity_level_id(level: LiquidityLevel) -> str:
    return f"LIQ-{level.kind}-{level.time}-{level.price:.5f}"


def sweep_event_id(setup_id: str, sweep: LiquiditySweepEvent) -> str:
    side = "BSL" if sweep.sweep_type == "BUY_SIDE" else "SSL"
    return f"SWEEP-{setup_id}-{side}-{sweep.sweep_time}"


def displacement_event_id(setup_id: str, start_time: int) -> str:
    return f"DISP-{setup_id}-{start_time}"


def mss_event_id(setup_id: str, confirmation_time: int) -> str:
    return f"MSS-{setup_id}-{confirmation_time}"


def entry_event_id(setup_id: str, fvg_id: str) -> str:
    return f"ENTRY-{setup_id}-{fvg_id}"


def swing_id(swing_type: str, swing_time: int, price: float) -> str:
    return f"SWING-{swing_type}-{swing_time}-{price:.5f}"
