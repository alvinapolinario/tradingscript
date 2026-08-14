"""Normalize EA / strategy blobs into StrategySignal records."""
from __future__ import annotations

import time
from typing import Any

from app.analysis.confluence.types import ConfluenceConfig, Direction, StrategySignal
from app.analysis.confluence.weights import DEFAULT_STRATEGY_WEIGHTS


def _u(val: Any) -> str:
    return str(val or "").strip().upper()


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _direction_from_text(*parts: Any) -> Direction:
    text = " ".join(_u(p) for p in parts if p)
    if not text or text in ("NO_TRADE", "NO SETUP", "NO_SETUP", "INVALID", "INVALIDATED", "EXPIRED"):
        return "NO_SETUP"
    if any(k in text for k in ("BUY", "LONG", "BULL", "BULLISH")):
        return "LONG"
    if any(k in text for k in ("SELL", "SHORT", "BEAR", "BEARISH")):
        return "SHORT"
    if "WAIT" in text or "WATCH" in text or "NEUTRAL" in text:
        return "NEUTRAL"
    return "NO_SETUP"


def _freshness(ts: int, now: float, cfg: ConfluenceConfig) -> float:
    if ts <= 0:
        return 0.0
    return max(0.0, now - float(ts))


def _weight(name: str, cfg: ConfluenceConfig) -> float:
    if cfg.strategy_weights:
        return float(cfg.strategy_weights.get(name, DEFAULT_STRATEGY_WEIGHTS.get(name, 0.75)))
    return float(DEFAULT_STRATEGY_WEIGHTS.get(name, 0.75))


def _signal(
    *,
    strategy: str,
    direction: Direction,
    confidence: float,
    status: str,
    cfg: ConfluenceConfig,
    timestamp: int = 0,
    freshness_sec: float = 0.0,
    evidence: list[str] | None = None,
    invalidation: list[str] | None = None,
    active: bool = True,
) -> StrategySignal:
    return StrategySignal(
        strategy=strategy,
        direction=direction,
        confidence=max(0.0, min(100.0, confidence)),
        status=status,
        evidence=evidence or [],
        invalidation=invalidation or [],
        timestamp=timestamp,
        freshness_sec=freshness_sec,
        weight=_weight(strategy, cfg),
        active=active,
    )


def normalize_ea_signals(ea: dict[str, Any], cfg: ConfluenceConfig | None = None, *, now: float | None = None) -> list[StrategySignal]:
    """Extract normalized strategy signals from a heartbeat-like EA payload."""
    st = cfg or ConfluenceConfig()
    now_ts = now if now is not None else time.time()
    out: list[StrategySignal] = []

    ict = ea.get("ict") if isinstance(ea.get("ict"), dict) else {}
    python_active = bool(ea.get("ict_python_engine"))
    ict_engine = _u(ict.get("engine_source"))
    if ict and not (ict_engine == "MQL5_LEGACY" and python_active):
        if ict.get("valid") or ict.get("analysis_active"):
            ts = int(ict.get("eval_bar_time") or ict.get("timestamp") or 0)
            htf = ict.get("htf_bias") if isinstance(ict.get("htf_bias"), dict) else {}
            state = _u(ict.get("state") or ict.get("setup_state") or ict.get("status") or "—")
            entry_ready = bool(ict.get("entry_ready")) or state in ("ENTRY_READY", "TRIGGERED")
            decision = _u(ict.get("decision"))
            direction = _direction_from_text(decision, ict.get("direction"), htf.get("direction"))
            conf = _f(ict.get("confidence_score") or ict.get("confidence"))
            if entry_ready and ict.get("causality_valid", True):
                if decision in ("BUY", "SELL"):
                    direction = "LONG" if decision == "BUY" else "SHORT"
                conf = max(conf, 65.0)
            elif state in ("MSS_CONFIRMED", "EXECUTION_FVG_FOUND", "WAITING_FOR_RETRACE"):
                direction = "NEUTRAL" if direction in ("LONG", "SHORT") else direction
                conf = min(conf, 60.0) if conf else 0.0
            reasons = ict.get("reasons") if isinstance(ict.get("reasons"), list) else []
            inv = ict.get("invalidations") if isinstance(ict.get("invalidations"), list) else []
            out.append(
                _signal(
                    strategy="ICT",
                    direction=direction,
                    confidence=conf,
                    status=state,
                    cfg=st,
                    timestamp=ts,
                    freshness_sec=_freshness(ts, now_ts, st),
                    evidence=[str(r) for r in reasons[:6]],
                    invalidation=[str(x) for x in inv[:4]],
                    active=entry_ready
                    and ict.get("causality_valid", True) is not False
                    and direction in ("LONG", "SHORT"),
                )
            )

    amd = ea.get("amd_ifvg") if isinstance(ea.get("amd_ifvg"), dict) else {}
    if amd.get("valid") or amd.get("analysis_active"):
        ts = int(amd.get("eval_bar_time") or amd.get("timestamp") or 0)
        direction = _direction_from_text(amd.get("decision"), amd.get("higher_timeframe_bias"))
        conf = _f(amd.get("confidence"))
        status = _u(amd.get("setup_state") or amd.get("amd_phase") or "—")
        reasoning = amd.get("reasoning") if isinstance(amd.get("reasoning"), list) else []
        out.append(
            _signal(
                strategy="AMD_IFVG",
                direction=direction,
                confidence=conf,
                status=status,
                cfg=st,
                timestamp=ts,
                freshness_sec=_freshness(ts, now_ts, st),
                evidence=[str(r) for r in reasoning[:6]],
            )
        )

    box = ea.get("box_theory") if isinstance(ea.get("box_theory"), dict) else {}
    if box.get("valid") or box.get("analysis_active"):
        ts = int(box.get("eval_bar_time") or box.get("timestamp") or 0)
        direction = _direction_from_text(box.get("signal"), box.get("direction"), box.get("htf_bias"))
        conf = _f(box.get("confidence_score") or box.get("confidence"))
        status = _u(box.get("box_status") or "—")
        reasons = box.get("reasons") if isinstance(box.get("reasons"), list) else []
        out.append(
            _signal(
                strategy="BOX_THEORY",
                direction=direction,
                confidence=conf,
                status=status,
                cfg=st,
                timestamp=ts,
                freshness_sec=_freshness(ts, now_ts, st),
                evidence=[str(r) for r in reasons[:6]],
            )
        )

    swing = ea.get("swing_strategy") if isinstance(ea.get("swing_strategy"), dict) else {}
    if swing.get("valid"):
        ts = int(swing.get("eval_bar_time") or swing.get("timestamp") or 0)
        direction = _direction_from_text(swing.get("signal"), swing.get("direction"))
        conf = _f(swing.get("confidence"))
        status = _u(swing.get("signal") or swing.get("entry_quality") or "—")
        out.append(
            _signal(
                strategy="SWING",
                direction=direction,
                confidence=conf,
                status=status[:40],
                cfg=st,
                timestamp=ts,
                freshness_sec=_freshness(ts, now_ts, st),
            )
        )

    gsm = ea.get("gold_smc") if isinstance(ea.get("gold_smc"), dict) else {}
    if gsm.get("analysis_active") or gsm.get("valid"):
        ts = int(gsm.get("eval_bar_time") or gsm.get("timestamp") or 0)
        setup = str(gsm.get("setup_type") or "")
        direction = _direction_from_text(setup, gsm.get("bias"), gsm.get("direction"))
        conf = _f(gsm.get("setup_score") or gsm.get("confidence_score"))
        if "NO VALID" in _u(setup):
            direction = "NO_SETUP"
            conf = 0.0
        out.append(
            _signal(
                strategy="GOLD_SMC",
                direction=direction,
                confidence=conf,
                status=setup[:40] or "—",
                cfg=st,
                timestamp=ts,
                freshness_sec=_freshness(ts, now_ts, st),
            )
        )

    lg = ea.get("liquidity_grab") if isinstance(ea.get("liquidity_grab"), dict) else {}
    if lg.get("valid"):
        ts = int(lg.get("eval_bar_time") or lg.get("timestamp") or 0)
        direction = _direction_from_text(lg.get("direction"), lg.get("side"), lg.get("status"))
        conf = _f(lg.get("confidence_score") or lg.get("confidence"))
        status = _u(lg.get("status") or lg.get("status_line") or "—")
        out.append(
            _signal(
                strategy="LIQUIDITY_GRAB",
                direction=direction,
                confidence=conf,
                status=status[:40],
                cfg=st,
                timestamp=ts,
                freshness_sec=_freshness(ts, now_ts, st),
            )
        )

    bos = ea.get("breakout_structure") if isinstance(ea.get("breakout_structure"), dict) else {}
    if bos.get("valid"):
        ts = int(bos.get("eval_bar_time") or bos.get("timestamp") or 0)
        grade = _u(bos.get("grade_label"))
        direction = _direction_from_text(bos.get("direction"), bos.get("breakout_direction"), grade)
        conf = _f(bos.get("confidence_score"))
        if grade == "REJECT":
            direction = "NO_SETUP"
            conf = min(conf, 40.0)
        out.append(
            _signal(
                strategy="BREAKOUT",
                direction=direction,
                confidence=conf,
                status=grade or "—",
                cfg=st,
                timestamp=ts,
                freshness_sec=_freshness(ts, now_ts, st),
            )
        )

    fvg_h4_m15 = ea.get("h4_m15_fvg") if isinstance(ea.get("h4_m15_fvg"), dict) else {}
    if fvg_h4_m15.get("valid"):
        primary = fvg_h4_m15.get("primary") if isinstance(fvg_h4_m15.get("primary"), dict) else {}
        if primary:
            ts = int(primary.get("entry_ready_time") or 0)
            state = _u(primary.get("state") or primary.get("decision"))
            direction = _direction_from_text(primary.get("direction"))
            conf = _f(primary.get("score"))
            entry_ready = state == "ENTRY_READY" or _u(primary.get("decision")) == "ENTRY_READY"
            if not entry_ready:
                direction = "NEUTRAL" if direction in ("LONG", "SHORT") else direction
                conf = min(conf, 55.0) if conf > 0 else 0.0
            reasons = primary.get("reasons") if isinstance(primary.get("reasons"), list) else []
            out.append(
                _signal(
                    strategy="H4_M15_FVG",
                    direction=direction if entry_ready else "NEUTRAL",
                    confidence=conf,
                    status=state or "MONITOR",
                    cfg=st,
                    timestamp=ts,
                    freshness_sec=_freshness(ts, now_ts, st),
                    evidence=[str(r) for r in reasons[:6]],
                    active=entry_ready and direction in ("LONG", "SHORT"),
                )
            )

    entry = _u(ea.get("new_entry_decision"))
    if entry:
        direction = _direction_from_text(entry)
        out.append(
            _signal(
                strategy="M30_CORE",
                direction=direction,
                confidence=70.0 if entry in ("BUY_ALLOWED", "SELL_ALLOWED") else 35.0,
                status=entry,
                cfg=st,
                timestamp=int(ea.get("server_time") or 0),
                freshness_sec=0.0,
            )
        )

    return out
