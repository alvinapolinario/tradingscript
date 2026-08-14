"""Post-sweep displacement leg detection — multi-candle, causally bounded."""
from __future__ import annotations

from app.analysis.ict.types import DisplacementEvent, IctConfig
from app.market_structure.types import Candle


def _bar_seconds(candles: list[Candle]) -> int:
    if len(candles) < 2:
        return 900
    diffs = [candles[i].time - candles[i - 1].time for i in range(1, len(candles)) if candles[i].time > candles[i - 1].time]
    if not diffs:
        return 900
    diffs.sort()
    return max(60, diffs[len(diffs) // 2])


def _candle_directional(c: Candle, bullish: bool) -> bool:
    if bullish:
        return c.close > c.open
    return c.close < c.open


def _candle_metrics(c: Candle, atr: float, bullish: bool) -> dict[str, float]:
    body = abs(c.close - c.open)
    rng = max(c.high - c.low, 1e-9)
    body_atr = body / atr if atr else 0.0
    range_atr = rng / atr if atr else 0.0
    body_ratio = body / rng
    close_loc = (c.close - c.low) / rng if bullish else (c.high - c.close) / rng
    return {
        "body": body,
        "range": rng,
        "body_atr": body_atr,
        "range_atr": range_atr,
        "body_ratio": body_ratio,
        "close_location": close_loc,
    }


def _meets_thresholds(metrics: dict[str, float], cfg: IctConfig, bullish: bool) -> bool:
    if metrics["body_atr"] < cfg.displacement_min_body_atr:
        return False
    if metrics["range_atr"] < cfg.displacement_min_range_atr:
        return False
    if metrics["body_ratio"] < cfg.displacement_min_body_ratio:
        return False
    if bullish and metrics["close_location"] < 0.35:
        return False
    if not bullish and metrics["close_location"] < 0.35:
        return False
    return True


def _quality_score(metrics: dict[str, float], bars_count: int) -> float:
    score = min(40.0, metrics["body_atr"] * 25.0)
    score += min(25.0, metrics["range_atr"] * 15.0)
    score += min(20.0, metrics["body_ratio"] * 20.0)
    score += min(15.0, metrics["close_location"] * 15.0)
    if bars_count > 1:
        score += min(10.0, bars_count * 2.0)
    return min(100.0, score)


def find_displacement_leg(
    candles: list[Candle],
    *,
    sweep_time: int,
    direction: str,
    setup_id: str,
    atr: float,
    cfg: IctConfig,
) -> DisplacementEvent | None:
    """Find first valid directional expansion leg after sweep (1–N candles)."""
    bullish = direction == "BULLISH"
    post = [c for c in candles if c.time >= sweep_time]
    if not post:
        return None

    bar_sec = _bar_seconds(candles)
    max_end = sweep_time + cfg.max_displacement_bars_after_sweep * bar_sec
    window = [c for c in post if c.time <= max_end][: cfg.max_displacement_bars_after_sweep]
    if not window:
        return None

    best: DisplacementEvent | None = None
    i = 0
    while i < len(window):
        if not _candle_directional(window[i], bullish):
            i += 1
            continue
        leg = [window[i]]
        j = i + 1
        while j < len(window) and len(leg) < cfg.max_displacement_bars_after_sweep:
            if _candle_directional(window[j], bullish):
                leg.append(window[j])
                j += 1
            else:
                break

        primary = max(leg, key=lambda c: abs(c.close - c.open))
        agg_high = max(c.high for c in leg)
        agg_low = min(c.low for c in leg)
        metrics = _candle_metrics(primary, atr, bullish)
        if not _meets_thresholds(metrics, cfg, bullish):
            i += 1
            continue

        dist = abs(primary.close - leg[0].open)
        event = DisplacementEvent(
            event_id=f"DISP-{setup_id}-{leg[0].time}",
            setup_id=setup_id,
            direction=direction,
            start_time=leg[0].time,
            end_time=leg[-1].time,
            primary_candle_time=primary.time,
            open_price=leg[0].open,
            close_price=leg[-1].close,
            high=agg_high,
            low=agg_low,
            body_size=metrics["body"],
            range_size=metrics["range"],
            atr=atr,
            body_atr_ratio=metrics["body_atr"],
            range_atr_ratio=metrics["range_atr"],
            body_to_range_ratio=metrics["body_ratio"],
            close_location=metrics["close_location"],
            distance_travelled=dist,
            distance_atr=dist / atr if atr else 0.0,
            bars_count=len(leg),
            structure_break=False,
            fvg_created=False,
            quality_score=_quality_score(metrics, len(leg)),
        )
        if best is None or event.quality_score > best.quality_score:
            best = event
        i = j if j > i + 1 else i + 1

    if best and best.quality_score < cfg.displacement_min_score:
        return None
    return best
