"""ICT structural stop loss and risk/reward."""
from __future__ import annotations

from typing import Any

from app.analysis.ict.types import IctConfig, LiquiditySweepEvent


def calculate_risk_plan(
    *,
    trade_bias: str,
    entry_price: float,
    sweep: LiquiditySweepEvent | None,
    atr_val: float,
    cfg: IctConfig,
) -> dict[str, Any]:
    if not sweep:
        return {"stop_loss": 0.0, "invalidation": 0.0, "risk_distance": 0.0, "reason": ""}

    buf = cfg.sl_buffer_atr * atr_val
    if trade_bias == "BEARISH":
        sl = sweep.sweep_price + buf
        reason = "Above swept buy-side liquidity"
        inv = sl
    else:
        sl = sweep.sweep_price - buf
        reason = "Below swept sell-side liquidity"
        inv = sl

    risk = abs(entry_price - sl)
    return {
        "stop_loss": round(sl, 2),
        "invalidation": round(inv, 2),
        "risk_distance": round(risk, 2),
        "reason": reason,
    }


def best_risk_reward(targets: list[dict[str, Any]]) -> float:
    if not targets:
        return 0.0
    return max(float(t.get("rr") or 0) for t in targets)
