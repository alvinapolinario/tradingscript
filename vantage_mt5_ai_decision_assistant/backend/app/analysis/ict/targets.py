"""ICT structural targets — liquidity objectives."""
from __future__ import annotations

from typing import Any

from app.analysis.ict.types import IctConfig, LiquidityLevel
from app.market_structure.types import Candle


def build_targets(
    *,
    trade_bias: str,
    entry_price: float,
    stop_loss: float,
    bsl_levels: list[LiquidityLevel],
    ssl_levels: list[LiquidityLevel],
    candles: list[Candle],
    cfg: IctConfig,
) -> list[dict[str, Any]]:
    risk = abs(entry_price - stop_loss)
    if risk <= 0:
        return []

    targets: list[dict[str, Any]] = []
    if trade_bias == "BEARISH":
        below = sorted([l.price for l in ssl_levels if l.price < entry_price], reverse=True)
        tp1 = entry_price - risk
        targets.append({"name": "TP1", "price": round(tp1, 2), "reason": "1R internal", "rr": 1.0})
        if below:
            tp2 = below[0]
            targets.append(
                {
                    "name": "TP2",
                    "price": round(tp2, 2),
                    "reason": "Internal SSL",
                    "rr": round((entry_price - tp2) / risk, 2),
                }
            )
            if len(below) > 1:
                targets.append(
                    {
                        "name": "External SSL",
                        "price": round(below[-1], 2),
                        "reason": "External sell-side liquidity",
                        "rr": round((entry_price - below[-1]) / risk, 2),
                    }
                )
        else:
            targets.append({"name": "TP2", "price": round(entry_price - 2 * risk, 2), "reason": "2R", "rr": 2.0})
    else:
        above = sorted([l.price for l in bsl_levels if l.price > entry_price])
        tp1 = entry_price + risk
        targets.append({"name": "TP1", "price": round(tp1, 2), "reason": "1R internal", "rr": 1.0})
        if above:
            tp2 = above[0]
            targets.append(
                {
                    "name": "TP2",
                    "price": round(tp2, 2),
                    "reason": "Internal BSL",
                    "rr": round((tp2 - entry_price) / risk, 2),
                }
            )
            if len(above) > 1:
                targets.append(
                    {
                        "name": "External BSL",
                        "price": round(above[-1], 2),
                        "reason": "External buy-side liquidity",
                        "rr": round((above[-1] - entry_price) / risk, 2),
                    }
                )
        else:
            targets.append({"name": "TP2", "price": round(entry_price + 2 * risk, 2), "reason": "2R", "rr": 2.0})

    return targets
