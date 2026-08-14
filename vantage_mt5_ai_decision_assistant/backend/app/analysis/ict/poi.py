"""ICT Phase 4 — OTE, causal order blocks, breaker confluence (advisory only)."""
from __future__ import annotations

from dataclasses import dataclass

from app.analysis.gold_smc_logic import ote_zone
from app.analysis.ict.types import DisplacementEvent, IctConfig, IctSetupContext
from app.market_structure.types import Candle


@dataclass
class OrderBlockZone:
    block_id: str
    direction: str  # BULLISH | BEARISH
    upper: float
    lower: float
    body_upper: float
    body_lower: float
    midpoint: float
    ce: float
    created_time: int
    timeframe: str
    with_sweep: bool
    with_structure: bool
    quality_score: float
    status: str = "FRESH"
    is_breaker: bool = False
    mitigation_pct: float = 0.0
    source_displacement_event_id: str = ""


def zones_overlap(z1_lo: float, z1_hi: float, z2_lo: float, z2_hi: float) -> bool:
    lo1, hi1 = min(z1_lo, z1_hi), max(z1_lo, z1_hi)
    lo2, hi2 = min(z2_lo, z2_hi), max(z2_lo, z2_hi)
    if hi1 <= lo1 or hi2 <= lo2:
        return False
    return lo1 <= hi2 and lo2 <= hi1


def _opposite_candle(c: Candle, bullish_displacement: bool) -> bool:
    if bullish_displacement:
        return c.close < c.open
    return c.close > c.open


def _directional_candle(c: Candle, bullish: bool) -> bool:
    if bullish:
        return c.close > c.open
    return c.close < c.open


def find_causal_order_block(
    candles: list[Candle],
    *,
    displacement: DisplacementEvent,
    sweep_time: int,
    direction: str,
    setup_id: str,
    atr: float,
    cfg: IctConfig,
    timeframe: str = "M15",
) -> OrderBlockZone | None:
    """Last opposite candle before displacement leg — causal OB origin."""
    if not cfg.enable_order_blocks:
        return None

    bullish = direction == "BULLISH"
    leg = [c for c in candles if displacement.start_time <= c.time <= displacement.end_time]
    if not leg:
        return None

    first = leg[0]
    idx = next((i for i, c in enumerate(candles) if c.time == first.time), -1)
    if idx <= 0:
        return None

    origin = candles[idx - 1]
    if origin.time < sweep_time:
        return None
    if not _directional_candle(first, bullish) or not _opposite_candle(origin, bullish):
        return None

    broke = False
    if idx >= 2:
        prior = candles[idx - 2]
        broke = first.close > prior.high if bullish else first.close < prior.low

    with_sweep = origin.time >= sweep_time
    quality = min(
        100.0,
        35.0 + displacement.quality_score * 0.45 + (10.0 if broke else 0.0) + (12.0 if with_sweep else 0.0),
    )
    if cfg.ob_require_sweep_origin and not with_sweep:
        quality *= 0.85

    upper = origin.high
    lower = origin.low
    body_upper = max(origin.open, origin.close)
    body_lower = min(origin.open, origin.close)
    ce = lower + 0.5 * (upper - lower)

    ob = OrderBlockZone(
        block_id=f"OB-{setup_id}-{origin.time}",
        direction=direction,
        upper=upper,
        lower=lower,
        body_upper=body_upper,
        body_lower=body_lower,
        midpoint=0.5 * (upper + lower),
        ce=ce,
        created_time=origin.time,
        timeframe=timeframe,
        with_sweep=with_sweep,
        with_structure=broke,
        quality_score=round(quality, 1),
        source_displacement_event_id=displacement.event_id,
    )
    update_ob_mitigation(ob, candles)
    _maybe_promote_breaker(ob, candles, atr, direction, cfg)
    return ob


def update_ob_mitigation(ob: OrderBlockZone, candles: list[Candle]) -> None:
    post = [c for c in candles if c.time > ob.created_time]
    if not post:
        ob.status = "FRESH"
        ob.mitigation_pct = 0.0
        return

    worst = 0.0
    invalidated = False
    span = max(ob.upper - ob.lower, 1e-9)

    for c in post:
        if ob.direction == "BULLISH":
            if c.low <= ob.upper:
                depth = (ob.upper - min(c.low, ob.lower)) / span
                worst = max(worst, depth)
            if c.close < ob.lower:
                invalidated = True
                break
        else:
            if c.high >= ob.lower:
                depth = (max(c.high, ob.upper) - ob.lower) / span
                worst = max(worst, depth)
            if c.close > ob.upper:
                invalidated = True
                break

    ob.mitigation_pct = round(max(0.0, min(100.0, worst * 100.0)), 1)
    if invalidated:
        ob.status = "INVALIDATED"
    elif ob.mitigation_pct >= 99.0:
        ob.status = "MITIGATED"
    elif ob.mitigation_pct >= 40.0:
        ob.status = "PARTIAL"
    elif ob.mitigation_pct > 0.0:
        ob.status = "TOUCHED"
    else:
        ob.status = "FRESH"


def _maybe_promote_breaker(
    ob: OrderBlockZone,
    candles: list[Candle],
    atr: float,
    trade_direction: str,
    cfg: IctConfig,
) -> None:
    if not cfg.enable_breaker or ob.status != "INVALIDATED":
        return

    post = [c for c in candles if c.time > ob.created_time]
    if len(post) < 1:
        return

    last = post[-1]
    body_atr = abs(last.close - last.open) / atr if atr else 0.0
    if body_atr < cfg.displacement_min_body_atr * 0.5:
        return

    if ob.direction == "BULLISH" and last.close < ob.lower and trade_direction == "BEARISH":
        ob.is_breaker = True
        ob.direction = "BEARISH"
        ob.status = "BREAKER"
        ob.quality_score = min(100.0, ob.quality_score + cfg.breaker_quality_bonus)
    elif ob.direction == "BEARISH" and last.close > ob.upper and trade_direction == "BULLISH":
        ob.is_breaker = True
        ob.direction = "BULLISH"
        ob.status = "BREAKER"
        ob.quality_score = min(100.0, ob.quality_score + cfg.breaker_quality_bonus)


def compute_impulse_ote(
    displacement: DisplacementEvent,
    trade_bias: str,
    price: float,
    cfg: IctConfig,
) -> dict[str, float | bool]:
    """OTE band from displacement impulse leg — confluence only, not a standalone setup."""
    if not cfg.enable_ote or displacement.high <= displacement.low:
        return {
            "ote_valid": False,
            "ote_low": 0.0,
            "ote_mid": 0.0,
            "ote_high": 0.0,
            "price_in_ote": False,
        }

    bias = "Bullish" if trade_bias == "BULLISH" else "Bearish"
    lo, mid, hi = ote_zone(
        bias,
        displacement.high,
        displacement.low,
        ote_low_pct=cfg.ote_low_pct,
        ote_mid_pct=cfg.ote_mid_pct,
        ote_high_pct=cfg.ote_high_pct,
    )
    valid = hi > lo
    in_ote = valid and lo <= price <= hi
    return {
        "ote_valid": valid,
        "ote_low": lo,
        "ote_mid": mid,
        "ote_high": hi,
        "price_in_ote": in_ote,
    }


def apply_poi_analysis(
    ctx: IctSetupContext,
    setup_candles: list[Candle],
    *,
    price: float,
    atr_setup: float,
    cfg: IctConfig,
    timeframe: str = "M15",
) -> None:
    """Populate OTE / OB / breaker confluence on context after displacement."""
    disp = ctx.displacement_event
    sweep = ctx.sweep
    if not disp or not sweep or not sweep.detected:
        return

    ote = compute_impulse_ote(disp, ctx.trade_bias, price, cfg)
    ctx.ote_valid = bool(ote["ote_valid"])
    ctx.ote_low = float(ote["ote_low"])
    ctx.ote_mid = float(ote["ote_mid"])
    ctx.ote_high = float(ote["ote_high"])
    ctx.price_in_ote = bool(ote["price_in_ote"])

    if ctx.order_block is None:
        ctx.order_block = find_causal_order_block(
            setup_candles,
            displacement=disp,
            sweep_time=sweep.sweep_time,
            direction=ctx.trade_bias,
            setup_id=ctx.setup_id,
            atr=atr_setup,
            cfg=cfg,
            timeframe=timeframe,
        )
    elif ctx.order_block:
        update_ob_mitigation(ctx.order_block, setup_candles)
        _maybe_promote_breaker(ctx.order_block, setup_candles, atr_setup, ctx.trade_bias, cfg)

    ctx.fvg_overlaps_ote = False
    ctx.poi_overlaps_ote = False
    ctx.fvg_overlaps_ob = False

    if ctx.ote_valid:
        if ctx.fvg:
            ctx.fvg_overlaps_ote = zones_overlap(ctx.fvg.lower, ctx.fvg.upper, ctx.ote_low, ctx.ote_high)
        if ctx.order_block:
            ctx.poi_overlaps_ote = zones_overlap(
                ctx.order_block.lower, ctx.order_block.upper, ctx.ote_low, ctx.ote_high,
            )
        if ctx.fvg and ctx.order_block:
            ctx.fvg_overlaps_ob = zones_overlap(
                ctx.fvg.lower, ctx.fvg.upper, ctx.order_block.lower, ctx.order_block.upper,
            )

    if ctx.ote_valid and (ctx.price_in_ote or ctx.fvg_overlaps_ote or ctx.poi_overlaps_ote):
        ctx.reasons.append(
            f"OTE confluence: band {ctx.ote_low:.2f}–{ctx.ote_high:.2f}"
            + (" · price in OTE" if ctx.price_in_ote else "")
            + (" · FVG∩OTE" if ctx.fvg_overlaps_ote else "")
            + (" · POI∩OTE" if ctx.poi_overlaps_ote else ""),
        )
    if ctx.order_block:
        ob = ctx.order_block
        label = "Breaker" if ob.is_breaker else "Order block"
        ctx.reasons.append(
            f"{label} {ob.direction} {ob.lower:.2f}–{ob.upper:.2f} ({ob.status}, Q={ob.quality_score:.0f}).",
        )


def order_block_to_dict(ob: OrderBlockZone | None) -> dict:
    if not ob:
        return {}
    return {
        "block_id": ob.block_id,
        "direction": ob.direction,
        "upper": ob.upper,
        "lower": ob.lower,
        "body_upper": ob.body_upper,
        "body_lower": ob.body_lower,
        "midpoint": ob.midpoint,
        "ce": ob.ce,
        "created_time": ob.created_time,
        "timeframe": ob.timeframe,
        "with_sweep": ob.with_sweep,
        "with_structure": ob.with_structure,
        "quality_score": ob.quality_score,
        "status": ob.status,
        "is_breaker": ob.is_breaker,
        "mitigation_pct": ob.mitigation_pct,
        "source_displacement_event_id": ob.source_displacement_event_id,
    }
