"""Risk / reward planning for Box Theory."""
from __future__ import annotations

from app.analysis.box_theory.breakout import BreakoutEvent
from app.analysis.box_theory.retest import RetestEvent
from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig


def calculate_risk_plan(
    *,
    box: BoxRange,
    breakout: BreakoutEvent,
    retest: RetestEvent | None,
    cfg: BoxStrategyConfig,
    atr_val: float,
) -> dict[str, float]:
    buffer = cfg.sl_buffer_atr * atr_val
    entry = retest.price if retest and retest.detected else breakout.price
    m1, m2, m3 = cfg.tp_multipliers

    if breakout.direction == "UP":
        if cfg.sl_mode == "BOX_OPPOSITE":
            sl = box.low - buffer
        elif cfg.sl_mode == "BOX_MID":
            sl = box.mid - buffer
        else:
            sl = box.high - buffer
        risk = max(entry - sl, atr_val * 0.1)
        tp1 = entry + m1 * box.height
        tp2 = entry + m2 * box.height
        tp3 = entry + m3 * box.height
    else:
        if cfg.sl_mode == "BOX_OPPOSITE":
            sl = box.high + buffer
        elif cfg.sl_mode == "BOX_MID":
            sl = box.mid + buffer
        else:
            sl = box.low + buffer
        risk = max(sl - entry, atr_val * 0.1)
        tp1 = entry - m1 * box.height
        tp2 = entry - m2 * box.height
        tp3 = entry - m3 * box.height

    reward = abs(tp2 - entry)
    rr = round(reward / risk, 2) if risk > 0 else 0.0
    return {
        "entry": round(entry, 2),
        "stop_loss": round(sl, 2),
        "tp1": round(tp1, 2),
        "tp2": round(tp2, 2),
        "tp3": round(tp3, 2),
        "risk_reward": rr,
        "invalidation": round(sl, 2),
    }
