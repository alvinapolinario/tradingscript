"""Box Theory — main analysis service (deterministic, no look-ahead)."""
from __future__ import annotations

import logging
from typing import Any

from app.analysis.amd_ifvg_logic import AmdIfvgConfig, detect_fvgs
from app.analysis.box_theory.breakout import detect_breakout
from app.analysis.box_theory.detector import detect_box
from app.analysis.box_theory.fakeout import detect_fakeout
from app.analysis.box_theory.liquidity import detect_liquidity_sweep
from app.analysis.box_theory.retest import detect_retest
from app.analysis.box_theory.risk import calculate_risk_plan
from app.analysis.box_theory.scorer import atr_expansion, htf_bias, score_signal, volume_confirmed
from app.analysis.box_theory.types import (
    BoxEvent,
    BoxStatus,
    BoxStrategyConfig,
    DEFAULT_BOX_STRATEGY_CONFIG,
    EntryMode,
    SignalDecision,
)
from app.analysis.box_theory.utils import atr, candles_from_payload, validate_candles
from app.analysis.gold_symbol_validator import is_approved_gold_symbol

_log = logging.getLogger(__name__)


def _box_log(msg: str, *, symbol: str, timeframe: str, signal_id: str = "") -> None:
    _log.info("[BOX] %s symbol=%s tf=%s signal_id=%s", msg, symbol, timeframe, signal_id)
    try:
        from app.monitor_state import monitor_store

        monitor_store.add_log("INFO", "box_theory", f"[BOX] {msg}", key=signal_id or symbol)
    except Exception:
        pass


def analyze_box_strategy(
    *,
    symbol: str,
    candles_box: list,
    candles_entry: list | None = None,
    candles_structure: list | None = None,
    bid: float = 0.0,
    cfg: BoxStrategyConfig | None = None,
) -> dict[str, Any]:
    st = cfg or DEFAULT_BOX_STRATEGY_CONFIG
    sym = (symbol or "XAUUSD").upper()
    gold_ok, base = is_approved_gold_symbol(sym)
    if not gold_ok and base not in st.allowed_symbols:
        return _disabled(sym, "Box Theory supports XAUUSD/Gold only.")

    err = validate_candles(candles_box)
    if err:
        return _empty(sym, f"Rejected: {err}")

    entry_c = candles_entry or candles_box
    struct_c = candles_structure or candles_box
    atr_box = atr(candles_box)
    price = bid or candles_box[-1].close

    box = detect_box(candles_box, st, atr_box)
    if not box:
        _box_log("No valid box", symbol=sym, timeframe=st.box_timeframe)
        return _result(
            sym,
            st,
            box_status=BoxStatus.FORMING,
            signal=SignalDecision.WAIT,
            confidence=0,
            reasons=["No valid consolidation box detected."],
            price=price,
        )

    if box.age_candles < st.min_box_candles:
        _box_log("Box forming", symbol=sym, timeframe=st.box_timeframe)
        return _result(
            sym,
            st,
            box=box,
            box_status=BoxStatus.FORMING,
            signal=SignalDecision.WAIT,
            confidence=box.quality_score * 0.4,
            reasons=["Box still forming."],
            price=price,
        )

    breakout = detect_breakout(box, candles_box, st, atr_box)
    fakeout = detect_fakeout(box, candles_box, box.end_time)

    if fakeout and not breakout:
        status = BoxStatus.BULL_TRAP if fakeout.trap == "BULL_TRAP" else BoxStatus.BEAR_TRAP
        sid = _signal_id(sym, box, "—", [fakeout.trap])
        _box_log(f"{fakeout.trap} detected", symbol=sym, timeframe=st.box_timeframe, signal_id=sid)
        return _result(
            sym,
            st,
            box=box,
            box_status=status,
            signal=SignalDecision.INVALID,
            confidence=0,
            reasons=[f"{fakeout.trap.replace('_', ' ')} detected."],
            price=price,
            events=[fakeout.trap],
        )

    if fakeout and breakout and fakeout.time >= breakout.time:
        status = BoxStatus.BULL_TRAP if fakeout.trap == "BULL_TRAP" else BoxStatus.BEAR_TRAP
        sid = _signal_id(sym, box, "—", [fakeout.trap])
        _box_log(f"{fakeout.trap} after breakout", symbol=sym, timeframe=st.box_timeframe, signal_id=sid)
        return _result(
            sym,
            st,
            box=box,
            box_status=status,
            signal=SignalDecision.INVALID,
            confidence=0,
            reasons=[f"{fakeout.trap.replace('_', ' ')} detected."],
            price=price,
            events=[fakeout.trap],
        )

    if not breakout:
        _box_log("Box detected — waiting for breakout", symbol=sym, timeframe=st.box_timeframe)
        return _result(
            sym,
            st,
            box=box,
            box_status=BoxStatus.VALID,
            signal=SignalDecision.WATCH,
            confidence=box.quality_score * 0.6,
            reasons=["Valid box — waiting for breakout."],
            price=price,
            events=[BoxEvent.BOX_DETECTED.value],
        )

    sweep = detect_liquidity_sweep(box, candles_box, st, atr_box, breakout.time)
    retest = detect_retest(box, breakout, entry_c, st, atr(entry_c))

    fvg_ok = False
    if st.fvg_confirmation:
        amd_cfg = AmdIfvgConfig(fvg_min_gap_atr=0.05)
        fvgs = detect_fvgs(entry_c, timeframe=st.entry_timeframe, atr=atr(entry_c), cfg=amd_cfg)
        if breakout.direction == "UP":
            fvg_ok = any(f.direction == "BULLISH" for f in fvgs[-3:])
        else:
            fvg_ok = any(f.direction == "BEARISH" for f in fvgs[-3:])

    htf = htf_bias(struct_c) if st.htf_confirmation else "NEUTRAL"
    vol_ok = volume_confirmed(candles_box)
    atr_ok = atr_expansion(candles_box)
    confidence, quality, reasons = score_signal(
        box=box,
        breakout=breakout,
        retest=retest,
        sweep=sweep,
        fvg_confirmed=fvg_ok,
        htf=htf,
        atr_expansion=atr_ok,
        volume_confirmed=vol_ok,
        cfg=st,
    )

    box_status = BoxStatus.BREAKOUT_UP if breakout.direction == "UP" else BoxStatus.BREAKOUT_DOWN
    events: list[str] = [
        BoxEvent.BOX_BREAKOUT.value if breakout.direction == "UP" else BoxEvent.BOX_BREAKDOWN.value
    ]
    signal = SignalDecision.WATCH
    require_retest = st.require_retest or st.entry_mode == EntryMode.BREAKOUT_RETEST_MODE.value

    if require_retest and not retest.detected:
        box_status = BoxStatus.RETESTING
        events.append(BoxEvent.RETEST_STARTED.value)
        signal = SignalDecision.WAIT
        reasons.append("Waiting for retest confirmation.")
        _box_log("Waiting for retest", symbol=sym, timeframe=st.box_timeframe)
    elif require_retest and retest.detected and not retest.confirmed:
        box_status = BoxStatus.RETESTING
        signal = SignalDecision.WAIT
        reasons.append("Retest detected — awaiting confirmation candle.")
        _box_log("Retest detected", symbol=sym, timeframe=st.box_timeframe)
    elif confidence >= st.minimum_signal_score:
        if breakout.direction == "UP":
            box_status = BoxStatus.CONFIRMED_BULLISH
            signal = SignalDecision.BUY
            events.append(BoxEvent.BUY_CONFIRMED.value)
            _box_log("BUY confirmed", symbol=sym, timeframe=st.box_timeframe)
        else:
            box_status = BoxStatus.CONFIRMED_BEARISH
            signal = SignalDecision.SELL
            events.append(BoxEvent.SELL_CONFIRMED.value)
            _box_log("SELL confirmed", symbol=sym, timeframe=st.box_timeframe)
    else:
        reasons.append(f"Signal rejected — confidence {confidence} below minimum {st.minimum_signal_score}.")
        _box_log("Signal rejected - insufficient confidence", symbol=sym, timeframe=st.box_timeframe)

    if st.block_countertrend and htf == "BEARISH" and signal == SignalDecision.BUY:
        signal = SignalDecision.WAIT
        reasons.append("Blocked: counter HTF bearish structure.")
    if st.block_countertrend and htf == "BULLISH" and signal == SignalDecision.SELL:
        signal = SignalDecision.WAIT
        reasons.append("Blocked: counter HTF bullish structure.")

    risk_plan: dict[str, float] = {}
    if signal in (SignalDecision.BUY, SignalDecision.SELL):
        risk_plan = calculate_risk_plan(box=box, breakout=breakout, retest=retest, cfg=st, atr_val=atr_box)

    if box.age_candles > st.max_box_age_candles:
        box_status = BoxStatus.EXPIRED
        signal = SignalDecision.INVALID
        reasons.append("Box expired — too old.")

    direction = "BUY" if signal == SignalDecision.BUY else ("SELL" if signal == SignalDecision.SELL else "—")

    return {
        "module": "box_theory",
        "version": "1.0",
        "strategy": "BOX_THEORY",
        "valid": True,
        "gold_symbol_valid": True,
        "engine_enabled": st.enabled,
        "analysis_active": True,
        "symbol": sym,
        "base_symbol": base or "XAUUSD",
        "timeframe": st.box_timeframe,
        "entry_timeframe": st.entry_timeframe,
        "structure_timeframe": st.structure_timeframe,
        "direction": direction,
        "status": box_status.value,
        "box_status": box_status.value,
        "signal": signal.value,
        "signal_quality": quality.value if confidence >= 50 else "LOW",
        "confidence_score": confidence,
        "confidence": confidence,
        "htf_bias": htf,
        "current_price": price,
        "box": {
            "high": box.high,
            "low": box.low,
            "mid": box.mid,
            "height": box.height,
            "upper_touches": box.upper_touches,
            "lower_touches": box.lower_touches,
            "age_candles": box.age_candles,
            "start_time": box.start_time,
            "end_time": box.end_time,
            "quality_score": box.quality_score,
        },
        "breakout": {
            "detected": breakout is not None,
            "direction": breakout.direction if breakout else "",
            "price": breakout.price if breakout else 0.0,
            "confirmed": breakout is not None and not breakout.wick_only,
            "time": breakout.time if breakout else 0,
        },
        "retest": {
            "detected": retest.detected,
            "confirmed": retest.confirmed,
            "price": retest.price,
            "candles_waited": retest.candles_waited,
        },
        "liquidity_sweep": {
            "detected": sweep.detected,
            "direction": sweep.direction,
            "sweep_price": sweep.sweep_price,
            "level": sweep.level,
        },
        "fvg_confirmation": fvg_ok,
        "entry": risk_plan.get("entry", 0.0),
        "stop_loss": risk_plan.get("stop_loss", 0.0),
        "tp1": risk_plan.get("tp1", 0.0),
        "tp2": risk_plan.get("tp2", 0.0),
        "tp3": risk_plan.get("tp3", 0.0),
        "risk_reward": risk_plan.get("risk_reward", 0.0),
        "invalidation": {"price": risk_plan.get("invalidation", 0.0), "reason": "Beyond structural invalidation"},
        "events": events,
        "reasons": reasons,
        "status_line": signal.value,
        "technical_narrative": "; ".join(reasons[:5]),
        "action_guidance": _action_guidance(signal, box_status),
        "eval_bar_time": candles_box[-1].time,
        "signal_id": _signal_id(sym, box, direction, events),
    }


def _signal_id(sym: str, box, direction: str, events: list[str]) -> str:
    ev = events[-1] if events else "BOX"
    return f"{sym}|{box.start_time}|{box.end_time}|{direction}|{ev}"


def _action_guidance(signal: SignalDecision, status: BoxStatus) -> str:
    if signal == SignalDecision.BUY:
        return "Bullish box breakout confirmed — analysis only, no auto-trade."
    if signal == SignalDecision.SELL:
        return "Bearish box breakdown confirmed — analysis only, no auto-trade."
    if status == BoxStatus.RETESTING:
        return "Waiting for retest confirmation."
    return "Monitoring box structure — no trade signal yet."


def _disabled(symbol: str, reason: str) -> dict[str, Any]:
    return {
        "module": "box_theory",
        "version": "1.0",
        "strategy": "BOX_THEORY",
        "valid": False,
        "gold_symbol_valid": False,
        "symbol": symbol,
        "signal": SignalDecision.INVALID.value,
        "disable_reason": reason,
        "reasons": [reason],
    }


def _empty(symbol: str, reason: str) -> dict[str, Any]:
    return {
        "module": "box_theory",
        "version": "1.0",
        "strategy": "BOX_THEORY",
        "valid": True,
        "gold_symbol_valid": True,
        "symbol": symbol,
        "signal": SignalDecision.WAIT.value,
        "box_status": BoxStatus.FORMING.value,
        "confidence_score": 0,
        "reasons": [reason],
    }


def _result(
    sym: str,
    st: BoxStrategyConfig,
    *,
    box=None,
    box_status: BoxStatus,
    signal: SignalDecision,
    confidence: float,
    reasons: list[str],
    price: float,
    events: list[str] | None = None,
) -> dict[str, Any]:
    quality = "LOW"
    if confidence >= 85:
        quality = "VERY HIGH"
    elif confidence >= 70:
        quality = "HIGH"
    elif confidence >= 50:
        quality = "MODERATE"
    payload: dict[str, Any] = {
        "module": "box_theory",
        "version": "1.0",
        "strategy": "BOX_THEORY",
        "valid": True,
        "gold_symbol_valid": True,
        "engine_enabled": st.enabled,
        "analysis_active": True,
        "symbol": sym,
        "timeframe": st.box_timeframe,
        "entry_timeframe": st.entry_timeframe,
        "structure_timeframe": st.structure_timeframe,
        "direction": "—",
        "status": box_status.value,
        "box_status": box_status.value,
        "signal": signal.value,
        "signal_quality": quality,
        "confidence_score": confidence,
        "confidence": confidence,
        "current_price": price,
        "events": events or [],
        "reasons": reasons,
        "status_line": signal.value,
        "technical_narrative": "; ".join(reasons),
        "action_guidance": _action_guidance(signal, box_status),
    }
    if box:
        payload["box"] = {
            "high": box.high,
            "low": box.low,
            "mid": box.mid,
            "height": box.height,
            "upper_touches": box.upper_touches,
            "lower_touches": box.lower_touches,
            "age_candles": box.age_candles,
        }
        payload["signal_id"] = _signal_id(sym, box, "—", events or [])
    return payload
