"""Restore ICT setup context from persisted analyze payload."""
from __future__ import annotations

from typing import Any

from app.analysis.ict.types import (
    DisplacementEvent,
    IctSetupContext,
    LiquiditySweepEvent,
    MssTarget,
    StructureBreakEvent,
)
from app.market_structure.types import FvgZone


def rehydrate_context_from_payload(ctx: IctSetupContext, payload: dict[str, Any]) -> None:
    """Merge event identity and lifecycle flags from last persisted payload."""
    if not payload:
        return

    le = payload.get("liquidity_event") or {}
    if le and ctx.sweep:
        ctx.sweep.event_id = str(le.get("event_id") or ctx.sweep.event_id)
        ctx.sweep.liquidity_level_id = str(le.get("liquidity_level_id") or ctx.sweep.liquidity_level_id)
        ctx.sweep.penetration_atr = float(le.get("penetration_atr") or ctx.sweep.penetration_atr)
        ctx.sweep.reclaim_confirmed = bool(le.get("reclaim", ctx.sweep.reclaim_confirmed))

    mt = payload.get("mss_target") or {}
    if mt.get("swing_id"):
        ctx.mss_target = MssTarget(
            swing_id=str(mt["swing_id"]),
            swing_type=str(mt.get("swing_type") or "HIGH"),
            price=float(mt.get("price") or 0),
            time=int(mt.get("time") or 0),
        )

    de = payload.get("displacement_event") or {}
    if de.get("event_id"):
        ctx.displacement_event = DisplacementEvent(
            event_id=str(de["event_id"]),
            setup_id=str(de.get("setup_id") or ctx.setup_id),
            direction=str(de.get("direction") or ctx.trade_bias),
            start_time=int(de.get("start_time") or 0),
            end_time=int(de.get("end_time") or 0),
            primary_candle_time=int(de.get("primary_candle_time") or de.get("start_time") or 0),
            open_price=float(de.get("open_price") or 0),
            close_price=float(de.get("close_price") or 0),
            high=float(de.get("high") or 0),
            low=float(de.get("low") or 0),
            body_size=float(de.get("body_size") or 0),
            range_size=float(de.get("range_size") or 0),
            atr=float(de.get("atr") or 0),
            body_atr_ratio=float(de.get("body_atr") or de.get("body_atr_ratio") or 0),
            range_atr_ratio=float(de.get("range_atr") or de.get("range_atr_ratio") or 0),
            body_to_range_ratio=float(de.get("body_to_range_ratio") or 0),
            close_location=float(de.get("close_location") or 0),
            distance_travelled=float(de.get("distance_travelled") or 0),
            distance_atr=float(de.get("distance_atr") or 0),
            bars_count=int(de.get("bars_count") or 1),
            structure_break=bool(de.get("structure_break")),
            fvg_created=bool(de.get("fvg_created")),
            quality_score=float(de.get("quality") or de.get("quality_score") or 0),
        )
        ctx.displacement_score = ctx.displacement_event.quality_score
        ctx.displacement_time = ctx.displacement_event.primary_candle_time

    me = payload.get("mss_event") or {}
    if me.get("event_id"):
        ctx.mss_event = StructureBreakEvent(
            event_id=str(me["event_id"]),
            setup_id=str(me.get("setup_id") or ctx.setup_id),
            type=str(me.get("type") or "MSS"),
            direction=str(me.get("direction") or ctx.trade_bias),
            broken_swing_id=str(me.get("broken_swing_id") or ""),
            broken_level=float(me.get("broken_level") or 0),
            broken_swing_time=int(me.get("broken_swing_time") or 0),
            confirmation_time=int(me.get("confirmation_time") or 0),
            confirmation_price=float(me.get("confirmation_price") or 0),
            confirmation_type=str(me.get("confirmation_type") or "CLOSE"),
            source_displacement_event_id=str(me.get("source_displacement_event_id") or ""),
            quality_score=float(me.get("quality_score") or 0),
        )
        ctx.mss = {
            "shift_detected": True,
            "direction": ctx.mss_event.direction,
            "broken_level": ctx.mss_event.broken_level,
            "broken_swing_id": ctx.mss_event.broken_swing_id,
            "broken_swing_time": ctx.mss_event.broken_swing_time,
            "confirmation_time": ctx.mss_event.confirmation_time,
            "confirmation_type": ctx.mss_event.confirmation_type,
            "quality_score": ctx.mss_event.quality_score,
            "source_displacement_event_id": ctx.mss_event.source_displacement_event_id,
        }

    fe = payload.get("execution_fvg") or {}
    if fe.get("fvg_id"):
        ctx.execution_fvg_id = str(fe["fvg_id"])
        ctx.fvg = FvgZone(
            fvg_id=str(fe["fvg_id"]),
            direction=str(fe.get("direction") or ctx.trade_bias),
            timeframe=str(payload.get("execution_timeframe") or "M5"),
            created_time=int(fe.get("created_time") or 0),
            lower=float(fe.get("lower") or 0),
            upper=float(fe.get("upper") or 0),
            gap_size=float(fe.get("gap_size") or abs(float(fe.get("upper") or 0) - float(fe.get("lower") or 0))),
            gap_atr=float(fe.get("gap_atr") or 0),
            displacement_score=float(fe.get("displacement_score") or 0),
            mitigation_pct=float(fe.get("mitigation_pct") or 0),
            symbol=str(payload.get("symbol") or ""),
            setup_id=str(ctx.setup_id),
            displacement_event_id=str(fe.get("displacement_event_id") or ""),
            mss_event_id=str(fe.get("mss_event_id") or ""),
            created_at=int(fe.get("created_time") or 0),
            updated_at=int(fe.get("created_time") or 0),
        )

    ctx.causality_valid = bool(payload.get("causality_valid", True))
    ctx.causality_errors = list(payload.get("causality_errors") or [])
    ctx.state_reason = str(payload.get("state_reason") or "")
    ctx.entry_ready_emitted = bool(payload.get("entry_ready") or payload.get("entry_ready_emitted"))
    ctx.entry_event_id = str(payload.get("entry_event_id") or ctx.entry_event_id)
    if payload.get("fvg_touch_time"):
        ctx.fvg_touch_time = int(payload["fvg_touch_time"])
    if payload.get("entry_ready_time"):
        ctx.entry_ready_time = int(payload["entry_ready_time"])

    ote = payload.get("ote") or {}
    if ote:
        ctx.ote_valid = bool(ote.get("valid"))
        ctx.ote_low = float(ote.get("ote_low") or 0)
        ctx.ote_mid = float(ote.get("ote_mid") or 0)
        ctx.ote_high = float(ote.get("ote_high") or 0)
        ctx.price_in_ote = bool(ote.get("price_in_ote"))
        ctx.fvg_overlaps_ote = bool(ote.get("fvg_overlaps_ote"))
        ctx.poi_overlaps_ote = bool(ote.get("poi_overlaps_ote"))

    ob = payload.get("order_block") or {}
    if ob.get("block_id"):
        from app.analysis.ict.poi import OrderBlockZone

        ctx.order_block = OrderBlockZone(
            block_id=str(ob["block_id"]),
            direction=str(ob.get("direction") or ctx.trade_bias),
            upper=float(ob.get("upper") or 0),
            lower=float(ob.get("lower") or 0),
            body_upper=float(ob.get("body_upper") or ob.get("upper") or 0),
            body_lower=float(ob.get("body_lower") or ob.get("lower") or 0),
            midpoint=float(ob.get("midpoint") or 0),
            ce=float(ob.get("ce") or 0),
            created_time=int(ob.get("created_time") or 0),
            timeframe=str(ob.get("timeframe") or "M15"),
            with_sweep=bool(ob.get("with_sweep")),
            with_structure=bool(ob.get("with_structure")),
            quality_score=float(ob.get("quality_score") or 0),
            status=str(ob.get("status") or "FRESH"),
            is_breaker=bool(ob.get("is_breaker")),
            mitigation_pct=float(ob.get("mitigation_pct") or 0),
            source_displacement_event_id=str(ob.get("source_displacement_event_id") or ""),
        )

    poi = payload.get("poi_confluence") or {}
    if poi:
        ctx.fvg_overlaps_ob = bool(poi.get("fvg_overlaps_ob"))
        ctx.fvg_overlaps_ote = bool(poi.get("fvg_overlaps_ote")) or ctx.fvg_overlaps_ote
        ctx.poi_overlaps_ote = bool(poi.get("poi_overlaps_ote")) or ctx.poi_overlaps_ote
