"""ICT bearish model — BSL sweep → displacement → MSS → FVG → SSL target."""
from __future__ import annotations

from app.analysis.ict.types import IctConfig, IctSetupContext, IctSetupState
from app.market_structure.displacement import score_displacement
from app.market_structure.fvg import detect_fvgs
from app.market_structure.structure import detect_mss
from app.market_structure.swings import find_swings
from app.market_structure.types import Candle


def evaluate_bearish_sequence(
    ctx: IctSetupContext,
    setup_candles: list[Candle],
    exec_candles: list[Candle],
    atr_setup: float,
    atr_exec: float,
    cfg: IctConfig,
    price: float,
) -> IctSetupContext:
    sweep = ctx.sweep
    if not sweep or sweep.trade_bias != "BEARISH":
        return ctx

    post = [c for c in setup_candles if c.time >= sweep.sweep_time]
    if len(post) < 2:
        ctx.state = IctSetupState.WAITING_FOR_DISPLACEMENT
        ctx.reasons.append("Waiting for bearish displacement after BSL sweep.")
        return ctx

    disp_candle = max(post, key=lambda c: score_displacement(c, atr_setup, False, False))
    disp_score = score_displacement(disp_candle, atr_setup, False, False)
    ctx.displacement_score = disp_score
    ctx.displacement_time = disp_candle.time

    if disp_score < cfg.displacement_min_score:
        ctx.state = IctSetupState.WAITING_FOR_DISPLACEMENT
        ctx.reasons.append(f"Bearish displacement score {disp_score:.0f} below threshold.")
        return ctx

    ctx.state = IctSetupState.DISPLACEMENT_CONFIRMED
    ctx.timeline.append({"step": "DISPLACEMENT", "status": "done"})
    ctx.reasons.append(f"Bearish displacement confirmed (score {disp_score:.0f}).")

    swings = find_swings(setup_candles, cfg.pivot_left, cfg.pivot_right, atr_setup, cfg.swing_min_atr)
    mss = detect_mss(setup_candles, swings, "BEARISH", atr_setup, cfg)
    if not mss or not mss.get("shift_detected"):
        ctx.state = IctSetupState.WAITING_FOR_MSS
        ctx.reasons.append("Waiting for bearish MSS.")
        return ctx

    ctx.mss = mss
    ctx.state = IctSetupState.MSS_CONFIRMED
    ctx.timeline.append({"step": "MSS", "status": "done"})
    ctx.reasons.append(f"Bearish MSS — broke {mss['broken_level']:.2f}.")

    fvgs = detect_fvgs(
        [c for c in exec_candles if c.time >= sweep.sweep_time],
        timeframe=cfg.primary_execution_timeframe,
        atr=atr_exec,
        cfg=cfg,
    )
    bear_fvgs = [f for f in fvgs if f.direction == "BEARISH"]
    if not bear_fvgs:
        ctx.state = IctSetupState.WAITING_FOR_RETRACE
        ctx.reasons.append("Waiting for bearish FVG formation.")
        return ctx

    ctx.fvg = bear_fvgs[-1]
    ctx.timeline.append({"step": "FVG", "status": "done"})
    _apply_entry_state(ctx, price, cfg, atr_exec)
    return ctx


def _apply_entry_state(ctx: IctSetupContext, price: float, cfg: IctConfig, atr_exec: float) -> None:
    from app.analysis.ict.entry import build_entry_zone

    fvg = ctx.fvg
    if not fvg:
        return
    zone = build_entry_zone(fvg, ctx.trade_bias)
    ctx.entry = zone
    if zone.zone_low <= price <= zone.zone_high:
        zone.status = "TOUCHED"
        ctx.state = IctSetupState.ENTRY_ZONE_ACTIVE
        ctx.reasons.append("Price inside bearish FVG entry zone.")
        if ctx.trade_bias == "BEARISH":
            ctx.state = IctSetupState.TRIGGERED
            zone.status = "CONFIRMED"
    elif price < zone.zone_low - cfg.chase_max_atr * atr_exec:
        ctx.state = IctSetupState.EXPIRED
        ctx.invalidations.append(f"Price chased below entry zone {zone.zone_low:.2f}")
    else:
        ctx.state = IctSetupState.WAITING_FOR_RETRACE
        ctx.reasons.append("Waiting for retrace into bearish FVG.")
