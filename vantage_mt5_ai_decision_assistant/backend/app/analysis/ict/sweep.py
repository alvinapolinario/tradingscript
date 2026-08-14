"""ICT liquidity sweep detection."""
from __future__ import annotations

from app.analysis.ict.types import IctConfig, LiquidityLevel, LiquiditySweepEvent
from app.market_structure.types import Candle


def detect_liquidity_sweep(
    candles: list[Candle],
    *,
    bsl_levels: list[LiquidityLevel],
    ssl_levels: list[LiquidityLevel],
    atr_val: float,
    cfg: IctConfig,
    after_time: int = 0,
) -> LiquiditySweepEvent | None:
    """Detect most recent meaningful BSL or SSL sweep after ``after_time``."""
    min_pen = cfg.sweep_min_penetration_atr * atr_val
    max_pen = cfg.sweep_max_penetration_atr * atr_val
    relevant = [c for c in candles if c.time > after_time][-20:] if after_time else candles[-20:]

    best: LiquiditySweepEvent | None = None
    for c in relevant:
        for lv in bsl_levels:
            pen = c.high - lv.price
            if min_pen <= pen <= max_pen and c.close < lv.price:
                reentry = not cfg.sweep_require_reentry or c.close <= lv.price
                if not reentry:
                    continue
                wick = c.high - max(c.open, c.close)
                body = abs(c.close - c.open) or 1e-9
                q = min(100.0, 55.0 + (wick / body) * 15.0 + pen / atr_val * 20.0)
                ev = LiquiditySweepEvent(
                    detected=True,
                    sweep_type="BUY_SIDE",
                    trade_bias="BEARISH",
                    level=lv.price,
                    sweep_price=c.high,
                    sweep_time=c.time,
                    penetration=pen,
                    closed_back_inside=c.close < lv.price,
                    quality_score=q,
                    liquidity_type=lv.kind,
                    reclaim_confirmed=c.close < lv.price,
                )
                if best is None or c.time >= best.sweep_time:
                    best = ev

        for lv in ssl_levels:
            pen = lv.price - c.low
            if min_pen <= pen <= max_pen and c.close > lv.price:
                reentry = not cfg.sweep_require_reentry or c.close >= lv.price
                if not reentry:
                    continue
                wick = min(c.open, c.close) - c.low
                body = abs(c.close - c.open) or 1e-9
                q = min(100.0, 55.0 + (wick / body) * 15.0 + pen / atr_val * 20.0)
                ev = LiquiditySweepEvent(
                    detected=True,
                    sweep_type="SELL_SIDE",
                    trade_bias="BULLISH",
                    level=lv.price,
                    sweep_price=c.low,
                    sweep_time=c.time,
                    penetration=pen,
                    closed_back_inside=c.close > lv.price,
                    quality_score=q,
                    liquidity_type=lv.kind,
                    reclaim_confirmed=c.close > lv.price,
                )
                if best is None or c.time >= best.sweep_time:
                    best = ev

    return best
