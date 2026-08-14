"""ICT liquidity map — BSL, SSL, equal highs/lows, true PDH/PDL."""
from __future__ import annotations

from app.analysis.ict.session_levels import compute_previous_day_levels
from app.analysis.ict.types import IctConfig, LiquidityLevel
from app.market_structure.swings import find_swings
from app.market_structure.types import Candle


def build_liquidity_levels(
    candles: list[Candle],
    atr_val: float,
    cfg: IctConfig,
    *,
    d1_candles: list[Candle] | None = None,
    eval_time: int | None = None,
) -> tuple[list[LiquidityLevel], list[LiquidityLevel], dict[str, float | str]]:
    """Return (BSL levels, SSL levels, pdh_pdl_meta)."""
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

    et = eval_time or (candles[-1].time if candles else 0)
    pdh, pdl, pd_time, pd_source = compute_previous_day_levels(candles, d1_candles, et, cfg)
    meta: dict[str, float | str] = {
        "pdh": 0.0,
        "pdl": 0.0,
        "pdh_pdl_source": "",
        "reference_time": 0,
    }
    if pdh is not None and pdl is not None and pdh > pdl:
        bsl.append(LiquidityLevel("PDH", pdh, pd_time, pd_source))
        ssl.append(LiquidityLevel("PDL", pdl, pd_time, pd_source))
        meta = {
            "pdh": pdh,
            "pdl": pdl,
            "pdh_pdl_source": pd_source,
            "reference_time": pd_time,
        }

    bsl = _dedupe_levels(bsl, eq_tol)
    ssl = _dedupe_levels(ssl, eq_tol)
    return bsl, ssl, meta


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
