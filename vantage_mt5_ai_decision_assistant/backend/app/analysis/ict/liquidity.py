"""ICT liquidity map — BSL, SSL, equal highs/lows from swings."""
from __future__ import annotations

from app.analysis.ict.types import IctConfig, LiquidityLevel
from app.market_structure.swings import find_swings
from app.market_structure.types import Candle


def build_liquidity_levels(
    candles: list[Candle],
    atr_val: float,
    cfg: IctConfig,
) -> tuple[list[LiquidityLevel], list[LiquidityLevel]]:
    """Return (BSL levels, SSL levels) from confirmed swing pivots."""
    swings = find_swings(
        candles,
        cfg.pivot_left,
        cfg.pivot_right,
        atr_val,
        cfg.swing_min_atr,
    )
    eq_tol = cfg.equal_high_low_tolerance_atr * atr_val
    bsl: list[LiquidityLevel] = []
    ssl: list[LiquidityLevel] = []
    highs = [s for s in swings if s["type"] == "HIGH"]
    lows = [s for s in swings if s["type"] == "LOW"]

    for s in highs[-6:]:
        bsl.append(LiquidityLevel("BSL", s["price"], s["time"], "SWING"))
    for s in lows[-6:]:
        ssl.append(LiquidityLevel("SSL", s["price"], s["time"], "SWING"))

    # Equal highs / lows — cluster swing levels within tolerance
    for i, a in enumerate(highs[-4:]):
        for b in highs[-4:][i + 1 :]:
            if abs(a["price"] - b["price"]) <= eq_tol:
                px = (a["price"] + b["price"]) / 2.0
                bsl.append(LiquidityLevel("EQH", px, max(a["time"], b["time"]), "EQUAL_HIGHS"))
    for i, a in enumerate(lows[-4:]):
        for b in lows[-4:][i + 1 :]:
            if abs(a["price"] - b["price"]) <= eq_tol:
                px = (a["price"] + b["price"]) / 2.0
                ssl.append(LiquidityLevel("EQL", px, max(a["time"], b["time"]), "EQUAL_LOWS"))

    # PDH/PDL when enough history (approximate last 96 M15 bars as day proxy if no D1)
    if len(candles) >= 24:
        day_window = candles[-96:] if len(candles) >= 96 else candles[-24:]
        pdh = max(c.high for c in day_window)
        pdl = min(c.low for c in day_window)
        bsl.append(LiquidityLevel("PDH", pdh, day_window[-1].time, "SESSION_DAY"))
        ssl.append(LiquidityLevel("PDL", pdl, day_window[-1].time, "SESSION_DAY"))

    # Dedupe nearby levels
    bsl = _dedupe_levels(bsl, eq_tol)
    ssl = _dedupe_levels(ssl, eq_tol)
    return bsl, ssl


def _dedupe_levels(levels: list[LiquidityLevel], tol: float) -> list[LiquidityLevel]:
    out: list[LiquidityLevel] = []
    for lv in sorted(levels, key=lambda x: x.price):
        if not out or abs(lv.price - out[-1].price) > tol:
            out.append(lv)
    return out


def nearest_bsl_above(price: float, levels: list[LiquidityLevel]) -> LiquidityLevel | None:
    cands = [l for l in levels if l.price > price]
    return min(cands, key=lambda l: l.price) if cands else None


def nearest_ssl_below(price: float, levels: list[LiquidityLevel]) -> LiquidityLevel | None:
    cands = [l for l in levels if l.price < price]
    return max(cands, key=lambda l: l.price) if cands else None
