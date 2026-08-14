"""Causal ICT sequence — sweep → displacement → MSS → execution FVG → retrace."""
from __future__ import annotations

from app.analysis.ict.displacement_leg import find_displacement_leg, _bar_seconds
from app.analysis.ict.entry import build_entry_zone, update_mitigation
from app.analysis.ict.entry_trigger import fvg_interaction_met
from app.analysis.ict.events import entry_event_id, mss_event_id, sweep_event_id, swing_id
from app.analysis.ict.poi import apply_poi_analysis
from app.analysis.ict.types import (
    EntryTriggerMode,
    IctConfig,
    IctSetupContext,
    IctSetupState,
    MssTarget,
    StructureBreakEvent,
)
from app.market_structure.fvg import detect_fvgs
from app.market_structure.swings import find_swings
from app.market_structure.types import Candle, FvgZone


def freeze_mss_target(
    candles: list[Candle],
    sweep_time: int,
    direction: str,
    atr: float,
    cfg: IctConfig,
) -> MssTarget | None:
    """Capture pre-sweep swing that MSS must break — no post-sweep swings allowed."""
    eligible = [c for c in candles if c.time <= sweep_time]
    if len(eligible) < cfg.pivot_left + cfg.pivot_right + 3:
        return None
    swings = find_swings(eligible, cfg.pivot_left, cfg.pivot_right, atr, cfg.swing_min_atr)
    if direction == "BULLISH":
        highs = [s for s in swings if s["type"] == "HIGH" and s["time"] < sweep_time]
        if not highs:
            return None
        target = highs[-1]
    else:
        lows = [s for s in swings if s["type"] == "LOW" and s["time"] < sweep_time]
        if not lows:
            return None
        target = lows[-1]
    return MssTarget(
        swing_id=swing_id(target["type"], target["time"], target["price"]),
        swing_type=target["type"],
        price=float(target["price"]),
        time=int(target["time"]),
    )


def detect_causal_mss(
    candles: list[Candle],
    *,
    displacement,
    mss_target: MssTarget,
    direction: str,
    setup_id: str,
    atr: float,
    cfg: IctConfig,
) -> StructureBreakEvent | None:
    """MSS must occur within displacement leg (+ optional delay), close-confirmed."""
    bar_sec = _bar_seconds(candles)
    max_end = displacement.end_time + cfg.max_mss_bars_after_displacement * bar_sec
    search = [c for c in candles if displacement.start_time <= c.time <= max_end]
    bullish = direction == "BULLISH"

    for c in search:
        if bullish:
            if c.close <= mss_target.price:
                continue
        else:
            if c.close >= mss_target.price:
                continue
        body = abs(c.close - c.open)
        q = min(100.0, 55.0 + (body / atr if atr else 0) * 20.0)
        return StructureBreakEvent(
            event_id=mss_event_id(setup_id, c.time),
            setup_id=setup_id,
            type="MSS",
            direction=direction,
            broken_swing_id=mss_target.swing_id,
            broken_level=mss_target.price,
            broken_swing_time=mss_target.time,
            confirmation_time=c.time,
            confirmation_price=c.close,
            confirmation_type="CLOSE",
            source_displacement_event_id=displacement.event_id,
            quality_score=q,
        )
    return None


def select_execution_fvg(
    exec_candles: list[Candle],
    *,
    direction: str,
    sweep_time: int,
    displacement,
    mss_event: StructureBreakEvent,
    setup_id: str,
    symbol: str,
    atr_exec: float,
    cfg: IctConfig,
) -> tuple[FvgZone | None, str]:
    """Return causal execution FVG or rejection reason."""
    bar_sec = _bar_seconds(exec_candles) if exec_candles else 300
    window_end = mss_event.confirmation_time + cfg.max_fvg_bars_after_mss * bar_sec

    fvgs = detect_fvgs(
        exec_candles,
        timeframe=cfg.primary_execution_timeframe,
        atr=atr_exec,
        cfg=cfg,
        symbol=symbol,
    )
    candidates: list[FvgZone] = []
    for f in fvgs:
        if f.direction != direction:
            continue
        if f.created_time < sweep_time:
            continue
        if f.created_time < displacement.start_time:
            continue
        if f.created_time > window_end:
            continue
        candidates.append(f)

    if not candidates:
        if any(f.direction == direction and f.created_time < sweep_time for f in fvgs):
            return None, "FVG_PRE_SWEEP"
        if any(
            f.direction == direction
            and sweep_time <= f.created_time < displacement.start_time
            for f in fvgs
        ):
            return None, "FVG_PRE_DISPLACEMENT"
        return None, "NO_CAUSAL_FVG"

    chosen = candidates[-1]
    chosen.setup_id = setup_id
    chosen.displacement_event_id = displacement.event_id
    chosen.mss_event_id = mss_event.event_id
    return chosen, ""


def evaluate_causal_sequence(
    ctx: IctSetupContext,
    setup_candles: list[Candle],
    exec_candles: list[Candle],
    atr_setup: float,
    atr_exec: float,
    cfg: IctConfig,
    price: float,
    *,
    symbol: str = "",
    prior_state: IctSetupState | None = None,
) -> IctSetupContext:
    """Run causal ICT lifecycle after liquidity sweep."""
    sweep = ctx.sweep
    if not sweep or not sweep.detected:
        return ctx

    direction = ctx.trade_bias
    if direction not in ("BULLISH", "BEARISH"):
        return ctx

    setup_id = ctx.setup_id or f"ICT-{symbol}-M15-{sweep.sweep_time}"
    if not sweep.event_id:
        sweep.event_id = sweep_event_id(setup_id, sweep)
        sweep.liquidity_level_id = f"LIQ-{sweep.sweep_type}-{sweep.sweep_time}-{sweep.level:.5f}"
        sweep.penetration_atr = sweep.penetration / atr_setup if atr_setup else 0.0
        sweep.reclaim_confirmed = sweep.closed_back_inside

    bar_sec = _bar_seconds(setup_candles)

    # Stage timeout: sweep → displacement
    post_sweep = [c for c in setup_candles if c.time >= sweep.sweep_time]
    if len(post_sweep) > cfg.max_bars_sweep_to_displacement:
        if not ctx.displacement_event and ctx.state in (
            IctSetupState.LIQUIDITY_SWEPT,
            IctSetupState.WAITING_FOR_DISPLACEMENT,
        ):
            ctx.causality_errors.append("DISPLACEMENT_TIMEOUT")
            ctx.state = IctSetupState.EXPIRED
            ctx.reasons.append("Displacement did not form within sweep→displacement window.")
            return ctx

    # Freeze MSS target at sweep
    if ctx.mss_target is None:
        ctx.mss_target = freeze_mss_target(setup_candles, sweep.sweep_time, direction, atr_setup, cfg)
        if ctx.mss_target:
            ctx.reasons.append(
                f"MSS target frozen: {ctx.mss_target.swing_type} @ {ctx.mss_target.price:.2f} "
                f"(time {ctx.mss_target.time})."
            )
        else:
            ctx.causality_errors.append("MSS_TARGET_UNAVAILABLE")
            ctx.reasons.append("No pre-sweep swing available for MSS target.")

    # Displacement leg
    if ctx.displacement_event is None:
        disp = find_displacement_leg(
            setup_candles,
            sweep_time=sweep.sweep_time,
            direction=direction,
            setup_id=setup_id,
            atr=atr_setup,
            cfg=cfg,
        )
        if not disp:
            ctx.state = IctSetupState.WAITING_FOR_DISPLACEMENT
            ctx.reasons.append("Waiting for directional displacement after sweep.")
            return ctx
        ctx.displacement_event = disp
        ctx.displacement_score = disp.quality_score
        ctx.displacement_time = disp.primary_candle_time
        ctx.state = IctSetupState.DISPLACEMENT_CONFIRMED
        ctx.reasons.append(
            f"{direction} displacement leg {disp.start_time}–{disp.end_time} "
            f"(quality {disp.quality_score:.0f})."
        )

    disp = ctx.displacement_event
    if disp:
        apply_poi_analysis(
            ctx,
            setup_candles,
            price=price,
            atr_setup=atr_setup,
            cfg=cfg,
            timeframe=cfg.primary_setup_timeframe,
        )

    # MSS within causal window
    if ctx.mss_event is None and ctx.mss_target:
        mss = detect_causal_mss(
            setup_candles,
            displacement=disp,
            mss_target=ctx.mss_target,
            direction=direction,
            setup_id=setup_id,
            atr=atr_setup,
            cfg=cfg,
        )
        if not mss:
            # displacement → MSS timeout
            mss_deadline = disp.end_time + cfg.max_mss_bars_after_displacement * bar_sec
            if setup_candles[-1].time > mss_deadline:
                ctx.causality_errors.append("MSS_TIMEOUT")
                ctx.state = IctSetupState.EXPIRED
                ctx.reasons.append("MSS not confirmed within displacement causal window.")
                return ctx
            ctx.state = IctSetupState.WAITING_FOR_MSS
            ctx.reasons.append("Waiting for MSS on frozen pre-sweep structure.")
            return ctx

        if mss.broken_swing_id != ctx.mss_target.swing_id:
            ctx.causality_errors.append("MSS_WRONG_STRUCTURE_TARGET")
            ctx.state = IctSetupState.WAITING_FOR_MSS
            ctx.reasons.append("Structure break did not target frozen pre-sweep swing.")
            return ctx

        ctx.mss_event = mss
        ctx.mss = {
            "shift_detected": True,
            "direction": mss.direction,
            "broken_level": mss.broken_level,
            "broken_swing_id": mss.broken_swing_id,
            "broken_swing_time": mss.broken_swing_time,
            "confirmation_time": mss.confirmation_time,
            "confirmation_type": mss.confirmation_type,
            "quality_score": mss.quality_score,
            "source_displacement_event_id": mss.source_displacement_event_id,
        }
        ctx.state = IctSetupState.MSS_CONFIRMED
        ctx.reasons.append(f"{direction} MSS close-confirmed @ {mss.broken_level:.2f}.")

    mss_ev = ctx.mss_event
    if not mss_ev:
        return ctx

    # Execution FVG
    if ctx.fvg is None:
        fvg, reject = select_execution_fvg(
            exec_candles,
            direction=direction,
            sweep_time=sweep.sweep_time,
            displacement=disp,
            mss_event=mss_ev,
            setup_id=setup_id,
            symbol=symbol,
            atr_exec=atr_exec,
            cfg=cfg,
        )
        if not fvg:
            mss_bar_sec = _bar_seconds(exec_candles) if exec_candles else bar_sec
            fvg_deadline = mss_ev.confirmation_time + cfg.max_bars_mss_to_fvg * mss_bar_sec
            if setup_candles[-1].time > fvg_deadline and reject:
                ctx.causality_errors.append(reject or "FVG_TIMEOUT")
            ctx.state = IctSetupState.WAITING_FOR_EXECUTION_FVG
            ctx.state_reason = reject or "NO_CAUSAL_FVG"
            ctx.reasons.append(f"No causal execution FVG ({reject or 'searching'}).")
            return ctx
        ctx.fvg = fvg
        ctx.execution_fvg_id = fvg.fvg_id
        ctx.state = IctSetupState.EXECUTION_FVG_FOUND
        ctx.reasons.append(f"Execution FVG {fvg.lower:.2f}–{fvg.upper:.2f} linked to impulse.")

    apply_poi_analysis(
        ctx,
        setup_candles,
        price=price,
        atr_setup=atr_setup,
        cfg=cfg,
        timeframe=cfg.primary_setup_timeframe,
    )
    _apply_entry_lifecycle(ctx, price, cfg, atr_exec, prior_state, exec_candles)
    return ctx


def _apply_entry_lifecycle(
    ctx: IctSetupContext,
    price: float,
    cfg: IctConfig,
    atr_exec: float,
    prior_state: IctSetupState | None,
    exec_candles: list | None = None,
) -> None:
    fvg = ctx.fvg
    if not fvg:
        return

    zone = build_entry_zone(fvg, ctx.trade_bias)
    ctx.entry = zone
    update_mitigation(fvg, price)

    if ctx.state not in (
        IctSetupState.EXECUTION_FVG_FOUND,
        IctSetupState.WAITING_FOR_RETRACE,
        IctSetupState.FVG_TOUCHED,
        IctSetupState.ENTRY_ZONE_ACTIVE,
        IctSetupState.ENTRY_READY,
        IctSetupState.TRIGGERED,
    ):
        ctx.state = IctSetupState.WAITING_FOR_RETRACE

    last_exec = exec_candles[-1] if exec_candles else None
    mode = cfg.entry_trigger_mode
    if isinstance(mode, str):
        try:
            mode = EntryTriggerMode(mode)
        except ValueError:
            mode = EntryTriggerMode.TOUCH

    touched, touch_kind = fvg_interaction_met(
        fvg, price=price, last_exec_candle=last_exec, mode=mode, atr_exec=atr_exec,
    )
    in_zone = touched
    chased = (
        (ctx.trade_bias == "BULLISH" and price > zone.zone_high + cfg.chase_max_atr * atr_exec)
        or (ctx.trade_bias == "BEARISH" and price < zone.zone_low - cfg.chase_max_atr * atr_exec)
    )

    if chased:
        ctx.state = IctSetupState.EXPIRED
        ctx.causality_errors.append("RETRACE_TIMEOUT")
        ctx.invalidations.append(f"Price chased away from FVG entry zone.")
        return

    if not in_zone:
        ctx.state = IctSetupState.WAITING_FOR_RETRACE
        ctx.reasons.append("Waiting for retrace into execution FVG.")
        return

    # Price interaction — distinct from formation
    zone.status = "TOUCHED"
    ctx.fvg_touch_time = ctx.fvg_touch_time or fvg.updated_at
    ctx.reasons.append(f"FVG interaction ({touch_kind or mode.value}).")

    if prior_state in (
        IctSetupState.FVG_TOUCHED,
        IctSetupState.ENTRY_ZONE_ACTIVE,
        IctSetupState.ENTRY_READY,
        IctSetupState.TRIGGERED,
    ):
        ctx.state = IctSetupState.ENTRY_ZONE_ACTIVE
        if not ctx.entry_ready_emitted:
            from app.analysis.ict.store import entry_ready_already_emitted, mark_entry_ready_emitted

            eid = entry_event_id(ctx.setup_id, fvg.fvg_id)
            if entry_ready_already_emitted(eid):
                ctx.entry_ready_emitted = True
                ctx.state = IctSetupState.ENTRY_READY
            else:
                ctx.state = IctSetupState.ENTRY_READY
                ctx.entry_ready_time = fvg.updated_at or fvg.created_time
                ctx.entry_event_id = eid
                ctx.entry_ready_emitted = True
                mark_entry_ready_emitted(eid)
                ctx.reasons.append("ENTRY_READY — advisory only, no order sent.")
    else:
        ctx.state = IctSetupState.FVG_TOUCHED
        ctx.reasons.append("Execution FVG touched — awaiting confirmation pass for ENTRY_READY.")
