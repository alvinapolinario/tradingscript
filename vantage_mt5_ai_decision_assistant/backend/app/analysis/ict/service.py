"""ICT strategy — main analysis service (deterministic, closed-bar only)."""
from __future__ import annotations

import logging
from typing import Any

from app.analysis.gold_symbol_validator import is_approved_gold_symbol
from app.analysis.ict.bias import compute_htf_bias
from app.analysis.ict.explain import build_explanation
from app.analysis.ict.liquidity import build_liquidity_levels
from app.analysis.ict.models.bearish import evaluate_bearish_sequence
from app.analysis.ict.models.bullish import evaluate_bullish_sequence
from app.analysis.ict.risk import best_risk_reward, calculate_risk_plan
from app.analysis.ict.scorer import decide_from_score, quality_band, score_ict_setup
from app.analysis.ict.session import get_session_context
from app.analysis.ict.state_machine import (
    build_timeline,
    check_expiration,
    check_invalidation,
    check_target_reached,
    context_to_record,
    make_setup_id,
    merge_state,
)
from app.analysis.ict.state_store import get_active_setup, save_setup, state_changed
from app.analysis.ict.history import record_ict_result
from app.analysis.ict.sweep import detect_liquidity_sweep
from app.analysis.ict.targets import build_targets
from app.analysis.ict.types import (
    DEFAULT_ICT_CONFIG,
    IctConfig,
    IctDecision,
    IctSetupContext,
    IctSetupState,
)
from app.market_structure import atr, candles_from_payload, premium_discount, validate_candles
from app.market_structure.types import Candle

_log = logging.getLogger(__name__)


def _ict_log(msg: str, *, symbol: str, setup_id: str = "") -> None:
    _log.info("[ICT] %s symbol=%s setup_id=%s", msg, symbol, setup_id)
    try:
        from app.monitor_state import monitor_store

        monitor_store.add_log("INFO", "ict", f"[ICT] {msg}", key=setup_id or symbol)
    except Exception:
        pass


def analyze_ict_strategy(
    *,
    symbol: str,
    candles_by_timeframe: dict[str, list[Candle]] | None = None,
    candles_setup: list[Candle] | None = None,
    candles_execution: list[Candle] | None = None,
    bid: float = 0.0,
    spread_points: float = 0.0,
    cfg: IctConfig | None = None,
) -> dict[str, Any]:
    """Run ICT analysis on closed OHLC arrays. No look-ahead."""
    st = cfg or DEFAULT_ICT_CONFIG
    sym = (symbol or "XAUUSD").upper()
    gold_ok, _base = is_approved_gold_symbol(sym)
    if not gold_ok and sym.split(".")[0] not in st.allowed_symbols:
        return _disabled(sym, "ICT supports XAUUSD/Gold only.")

    tf_map: dict[str, list[Candle]] = dict(candles_by_timeframe or {})
    setup = candles_setup or tf_map.get(st.primary_setup_timeframe) or []
    execution = candles_execution or tf_map.get(st.primary_execution_timeframe) or setup

    if not setup:
        for tf in st.setup_timeframes:
            if tf_map.get(tf):
                setup = tf_map[tf]
                break
    if not execution:
        for tf in st.execution_timeframes:
            if tf_map.get(tf):
                execution = tf_map[tf]
                break

    err = validate_candles(setup)
    if err:
        return _empty(sym, f"Rejected: {err}")
    if len(setup) < st.min_candles:
        return _empty(sym, f"Need at least {st.min_candles} setup candles.")

    err_exec = validate_candles(execution) if execution is not setup else None
    if err_exec:
        return _empty(sym, f"Rejected execution TF: {err_exec}")

    atr_setup = atr(setup)
    atr_exec = atr(execution) if execution else atr_setup
    price = bid or setup[-1].close
    warnings: list[str] = []

    if spread_points > st.max_spread_points:
        warnings.append(f"Spread {spread_points} exceeds max {st.max_spread_points}")

    # HTF bias
    if not tf_map:
        tf_map = {st.primary_setup_timeframe: setup, st.primary_execution_timeframe: execution}
    htf, htf_conf, htf_evidence = compute_htf_bias(tf_map, st)

    # Liquidity map on setup TF
    bsl, ssl = build_liquidity_levels(setup, atr_setup, st)
    ctx = IctSetupContext(trade_bias="NEUTRAL", state=IctSetupState.WAITING_FOR_LIQUIDITY)
    ctx.bsl_levels = bsl
    ctx.ssl_levels = ssl
    ctx.htf_bias = htf
    ctx.htf_evidence = htf_evidence

    if bsl or ssl:
        ctx.state = IctSetupState.LIQUIDITY_IDENTIFIED
        ctx.reasons.append(f"Liquidity mapped: {len(bsl)} BSL / {len(ssl)} SSL levels.")

    # Session
    sess = get_session_context(setup[-1].time, setup, st)
    ctx.session_name = sess["session"]
    session_score = 70.0 if sess["session"] in ("LONDON", "NEW_YORK") else 40.0

    # Sweep on setup TF
    sweep = detect_liquidity_sweep(
        setup,
        bsl_levels=bsl,
        ssl_levels=ssl,
        atr_val=atr_setup,
        cfg=st,
    )
    if sweep:
        ctx.sweep = sweep
        ctx.trade_bias = sweep.trade_bias
        ctx.state = IctSetupState.LIQUIDITY_SWEPT
        ctx.reasons.append(
            f"{sweep.sweep_type} sweep at {sweep.sweep_price:.2f} (level {sweep.level:.2f})."
        )
        _ict_log(f"Sweep {sweep.sweep_type}", symbol=sym)
    else:
        ctx.reasons.append("No liquidity sweep detected on closed bars.")
        return _finalize(
            sym, st, ctx, price, htf_conf, session_score, warnings, setup, execution,
        )

    # Dealing range for premium/discount
    lookback = setup[-48:] if len(setup) >= 48 else setup
    ctx.dealing_high = max(c.high for c in lookback)
    ctx.dealing_low = min(c.low for c in lookback)
    ctx.premium_discount_zone = premium_discount(ctx.dealing_high, ctx.dealing_low, price)

    # Directional sequence
    if ctx.trade_bias == "BEARISH":
        ctx = evaluate_bearish_sequence(ctx, setup, execution, atr_setup, atr_exec, st, price)
    elif ctx.trade_bias == "BULLISH":
        ctx = evaluate_bullish_sequence(ctx, setup, execution, atr_setup, atr_exec, st, price)

    # Merge with persisted state (same sweep setup — do not regress)
    active = get_active_setup(sym, st.primary_setup_timeframe)
    setup_id = make_setup_id(sym, st.primary_setup_timeframe, ctx.sweep, ctx.trade_bias)
    ctx.setup_id = setup_id
    if active and active.setup_id == setup_id:
        ctx.state = merge_state(active.state, ctx.state)
        if active.state in (IctSetupState.TRIGGERED, IctSetupState.ENTRY_ZONE_ACTIVE):
            ctx.reasons.append(f"Resuming setup {setup_id} at {ctx.state.value}.")

    return _finalize(sym, st, ctx, price, htf_conf, session_score, warnings, setup, execution)


def _finalize(
    sym: str,
    st: IctConfig,
    ctx: IctSetupContext,
    price: float,
    htf_conf: float,
    session_score: float,
    warnings: list[str],
    setup: list[Candle],
    execution: list[Candle],
) -> dict[str, Any]:
    htf_aligned = (
        (ctx.trade_bias == "BEARISH" and ctx.htf_bias == "BEARISH")
        or (ctx.trade_bias == "BULLISH" and ctx.htf_bias == "BULLISH")
    )

    entry_price = ctx.entry.midpoint if ctx.entry else price
    risk_plan = calculate_risk_plan(
        trade_bias=ctx.trade_bias,
        entry_price=entry_price,
        sweep=ctx.sweep,
        atr_val=atr(setup),
        cfg=st,
    )
    targets = build_targets(
        trade_bias=ctx.trade_bias,
        entry_price=entry_price,
        stop_loss=float(risk_plan.get("stop_loss") or 0),
        bsl_levels=ctx.bsl_levels,
        ssl_levels=ctx.ssl_levels,
        candles=setup,
        cfg=st,
    )
    rr = best_risk_reward(targets)
    inv_price = float(risk_plan.get("invalidation") or risk_plan.get("stop_loss") or 0)

    # Lifecycle checks (order: invalidation → expiration → target)
    if not check_invalidation(ctx, price, setup, st, inv_price):
        check_expiration(ctx, setup, st)
    check_target_reached(ctx, price, targets)

    score, components, gates, penalties = score_ict_setup(
        ctx,
        htf_confidence=htf_conf,
        htf_aligned=htf_aligned,
        session_score=session_score,
        risk_reward=rr,
        cfg=st,
    )

    decision = decide_from_score(
        state=ctx.state,
        score=score,
        risk_reward=rr,
        gates=gates,
        htf_aligned=htf_aligned,
        trade_bias=ctx.trade_bias,
        cfg=st,
    )

    if risk_plan.get("invalidation") and f"{st.primary_setup_timeframe} close" not in " ".join(ctx.invalidations):
        ctx.invalidations.append(
            f"{st.primary_setup_timeframe} close beyond {risk_plan['invalidation']:.2f}"
        )

    timeline = build_timeline(ctx)
    setup_id = ctx.setup_id or make_setup_id(sym, st.primary_setup_timeframe, ctx.sweep, ctx.trade_bias)
    tp1 = float(targets[0]["price"]) if targets else 0.0
    eval_time = setup[-1].time

    record = context_to_record(
        ctx,
        symbol=sym,
        timeframe=st.primary_setup_timeframe,
        setup_id=setup_id,
        confidence=score,
        setup_candles=setup,
        stop_loss=float(risk_plan.get("stop_loss") or 0),
        tp1=tp1,
        eval_time=eval_time,
    )
    save_setup(record)

    narrative = build_explanation(ctx, decision, score, rr)
    state_changed_flag = state_changed(setup_id, ctx.state.value)
    if state_changed_flag:
        _ict_log(f"State change → {ctx.state.value}", symbol=sym, setup_id=setup_id)

    _ict_log(f"State={ctx.state.value} decision={decision.value} score={score}", symbol=sym, setup_id=setup_id)

    payload = {
        "module": "ict",
        "version": "1.0",
        "strategy": "ICT",
        "valid": True,
        "gold_symbol_valid": True,
        "engine_enabled": st.enabled,
        "analysis_active": True,
        "symbol": sym,
        "timeframe": st.primary_setup_timeframe,
        "execution_timeframe": st.primary_execution_timeframe,
        "timestamp": setup[-1].time,
        "status": ctx.state.value,
        "setup_state": ctx.state.value,
        "decision": decision.value,
        "direction": decision.value if decision in (IctDecision.BUY, IctDecision.SELL) else ctx.trade_bias,
        "confidence": score,
        "confidence_score": score,
        "signal_quality": quality_band(score),
        "score_components": components,
        "score_gates": gates,
        "score_penalties": penalties,
        "state_changed": state_changed_flag,
        "setup_record": {
            "setup_id": record.setup_id,
            "age_candles": record.age_candles,
            "created_time": record.created_time,
            "updated_time": record.updated_time,
            "last_event": record.last_event,
        },
        "htf_bias": {
            "direction": ctx.htf_bias,
            "confidence": round(htf_conf, 1),
            "evidence": ctx.htf_evidence,
        },
        "liquidity": {
            "bsl_count": len(ctx.bsl_levels),
            "ssl_count": len(ctx.ssl_levels),
            "sweep_detected": bool(ctx.sweep and ctx.sweep.detected),
            "type": ctx.sweep.sweep_type if ctx.sweep else "",
            "level": ctx.sweep.level if ctx.sweep else 0.0,
            "sweep_price": ctx.sweep.sweep_price if ctx.sweep else 0.0,
            "quality_score": ctx.sweep.quality_score if ctx.sweep else 0.0,
        },
        "structure": {
            "displacement": ctx.displacement_score >= st.displacement_min_score,
            "displacement_score": round(ctx.displacement_score, 1),
            "mss": ctx.mss.get("direction") if ctx.mss else "",
            "mss_detail": ctx.mss or {"shift_detected": False},
        },
        "fvg": {
            "direction": ctx.fvg.direction if ctx.fvg else "",
            "high": ctx.fvg.upper if ctx.fvg else 0.0,
            "low": ctx.fvg.lower if ctx.fvg else 0.0,
            "midpoint": ctx.fvg.midpoint if ctx.fvg else 0.0,
            "mitigation": ctx.fvg.mitigation_pct if ctx.fvg else 0.0,
            "fvg_id": ctx.fvg.fvg_id if ctx.fvg else "",
        },
        "entry": {
            "type": ctx.entry.type if ctx.entry else "",
            "direction": ctx.entry.direction if ctx.entry else "",
            "zone_high": ctx.entry.zone_high if ctx.entry else 0.0,
            "zone_low": ctx.entry.zone_low if ctx.entry else 0.0,
            "midpoint": ctx.entry.midpoint if ctx.entry else 0.0,
            "status": ctx.entry.status if ctx.entry else "",
        },
        "stop_loss": {
            "price": risk_plan.get("stop_loss", 0.0),
            "reason": risk_plan.get("reason", ""),
        },
        "targets": targets,
        "risk_reward": round(rr, 2),
        "premium_discount_zone": ctx.premium_discount_zone,
        "session": ctx.session_name,
        "reasons": ctx.reasons or ["Scanning for ICT setup on closed bars."],
        "invalidations": ctx.invalidations,
        "timeline": timeline,
        "warnings": warnings,
        "technical_narrative": narrative,
        "action_guidance": _action_guidance(decision, ctx.state),
        "setup_id": setup_id,
        "current_price": price,
        "eval_bar_time": setup[-1].time,
    }
    record_ict_result(sym, payload)
    return payload


def _action_guidance(decision: IctDecision, state: IctSetupState) -> str:
    if decision == IctDecision.BUY:
        return "Bullish ICT setup validated — analysis only, no auto-trade."
    if decision == IctDecision.SELL:
        return "Bearish ICT setup validated — analysis only, no auto-trade."
    if state == IctSetupState.WAITING_FOR_RETRACE:
        return "Waiting for retrace into FVG entry zone."
    if state == IctSetupState.ENTRY_ZONE_ACTIVE:
        return "Entry zone active — confirm on closed candle."
    return "Monitoring ICT sequence — no trade signal yet."


def _disabled(symbol: str, reason: str) -> dict[str, Any]:
    return {
        "module": "ict",
        "version": "1.0",
        "strategy": "ICT",
        "valid": False,
        "gold_symbol_valid": False,
        "engine_enabled": False,
        "analysis_active": False,
        "symbol": symbol,
        "decision": IctDecision.NO_TRADE.value,
        "setup_state": IctSetupState.NO_SETUP.value,
        "confidence": 0.0,
        "reasons": [reason],
    }


def _empty(symbol: str, reason: str) -> dict[str, Any]:
    return {
        "module": "ict",
        "version": "1.0",
        "strategy": "ICT",
        "valid": True,
        "gold_symbol_valid": True,
        "engine_enabled": True,
        "analysis_active": False,
        "symbol": symbol,
        "decision": IctDecision.WAIT.value,
        "setup_state": IctSetupState.WAITING_FOR_LIQUIDITY.value,
        "confidence": 0.0,
        "reasons": [reason],
    }


__all__ = ["analyze_ict_strategy", "candles_from_payload"]
