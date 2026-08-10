"""Box range detection."""
from __future__ import annotations

from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig, Candle
from app.analysis.box_theory.utils import atr


def detect_box(
    candles: list[Candle],
    cfg: BoxStrategyConfig,
    atr_val: float | None = None,
) -> BoxRange | None:
    """Detect a valid consolidation box on closed bars only."""
    if len(candles) < cfg.lookback_candles:
        return None
    window = candles[-cfg.lookback_candles :]
    atr_v = atr_val or atr(window)
    tol = cfg.touch_tolerance_atr * atr_v

    best: BoxRange | None = None
    for span in range(cfg.min_box_candles, min(len(window), cfg.lookback_candles) + 1):
        seg = window[-span:]
        hi = max(c.high for c in seg)
        lo = min(c.low for c in seg)
        height = hi - lo
        if height < cfg.min_box_height_atr * atr_v:
            continue
        if height > cfg.max_box_height_atr * atr_v:
            continue

        upper = sum(1 for c in seg if abs(c.high - hi) <= tol or abs(c.close - hi) <= tol)
        lower = sum(1 for c in seg if abs(c.low - lo) <= tol or abs(c.close - lo) <= tol)
        if upper < cfg.min_touches or lower < cfg.min_touches:
            continue

        inside = sum(1 for c in seg if lo <= c.close <= hi)
        inside_ratio = inside / len(seg)
        if inside_ratio < cfg.min_inside_ratio:
            continue

        quality = min(
            100.0,
            40.0
            + min(20.0, upper * 5.0)
            + min(20.0, lower * 5.0)
            + inside_ratio * 20.0,
        )
        candidate = BoxRange(
            box_id=f"BOX-{seg[0].time}-{seg[-1].time}",
            high=hi,
            low=lo,
            mid=(hi + lo) / 2.0,
            height=height,
            start_time=seg[0].time,
            end_time=seg[-1].time,
            age_candles=span,
            upper_touches=upper,
            lower_touches=lower,
            inside_ratio=round(inside_ratio, 3),
            quality_score=round(quality, 1),
        )
        if best is None or candidate.quality_score > best.quality_score:
            best = candidate
    return best
