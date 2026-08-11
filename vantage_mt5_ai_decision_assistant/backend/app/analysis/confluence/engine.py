"""Multi-strategy confluence engine."""
from __future__ import annotations

from typing import Any

from app.analysis.confluence.normalize import normalize_ea_signals
from app.analysis.confluence.types import ConfluenceConfig, ConfluenceResult, Direction, StrategySignal
from app.analysis.confluence.weights import DEFAULT_STRATEGY_WEIGHTS


def collect_confluence_signals(ea: dict[str, Any], cfg: ConfluenceConfig | None = None) -> list[StrategySignal]:
    """EA strategy signals plus optional MACRO signal when market news is enabled."""
    st = cfg or ConfluenceConfig()
    signals = normalize_ea_signals(ea, st)
    try:
        from app.market_news.confluence_signal import normalize_macro_signal

        macro = normalize_macro_signal(ea, st)
        if macro:
            signals.append(macro)
    except Exception:
        pass
    return signals


def _dominant_technical_direction(
    signals: list[StrategySignal],
    cfg: ConfluenceConfig,
) -> Direction:
    score_long = 0.0
    score_short = 0.0
    for sig in signals:
        if sig.strategy == "MACRO" or not sig.active or sig.direction not in ("LONG", "SHORT"):
            continue
        eff = _effective_weight(sig, cfg)
        contrib = eff * sig.confidence
        if sig.direction == "LONG":
            score_long += contrib
        else:
            score_short += contrib
    margin = abs(score_long - score_short)
    if margin < cfg.neutral_threshold:
        return "NEUTRAL"
    return "LONG" if score_long > score_short else "SHORT"


def _freshness_factor(sig: StrategySignal, cfg: ConfluenceConfig) -> float:
    if sig.freshness_sec <= 0:
        return 1.0
    if sig.freshness_sec <= cfg.freshness_threshold_sec:
        return 1.0
    return max(0.2, cfg.stale_weight_factor)


def _effective_weight(sig: StrategySignal, cfg: ConfluenceConfig) -> float:
    if not sig.active or sig.direction in ("NO_SETUP",):
        return 0.0
    base = sig.weight * _freshness_factor(sig, cfg)
    if sig.direction == "NEUTRAL":
        return base * 0.35
    return base


def _component(sig: StrategySignal, cfg: ConfluenceConfig, *, contribution: float) -> dict[str, Any]:
    return {
        "direction": sig.direction,
        "confidence": round(sig.confidence, 1),
        "status": sig.status,
        "weight": sig.weight,
        "freshness_sec": round(sig.freshness_sec, 1),
        "contribution": round(contribution, 2),
        "evidence": sig.evidence[:4],
        "invalidation": sig.invalidation[:3],
    }


def compute_confluence(signals: list[StrategySignal], cfg: ConfluenceConfig | None = None) -> ConfluenceResult:
    """Weighted confluence across normalized strategy signals."""
    st = cfg or ConfluenceConfig()

    active = [s for s in signals if s.active and s.direction != "NO_SETUP"]
    directional = [s for s in active if s.direction in ("LONG", "SHORT")]

    score_long = 0.0
    score_short = 0.0
    components: dict[str, dict] = {}
    strongest = ("", 0.0)

    for sig in signals:
        eff = _effective_weight(sig, st)
        contrib = eff * sig.confidence
        components[sig.strategy] = _component(sig, st, contribution=contrib)
        if sig.direction == "LONG":
            score_long += contrib
        elif sig.direction == "SHORT":
            score_short += contrib
        if contrib > strongest[1]:
            strongest = (sig.strategy, contrib)

    long_names = {s.strategy for s in directional if s.direction == "LONG"}
    short_names = {s.strategy for s in directional if s.direction == "SHORT"}
    conflicts = sorted(long_names | short_names) if long_names and short_names else []

    overall: Direction = "NEUTRAL"
    margin = abs(score_long - score_short)
    if margin >= st.neutral_threshold:
        overall = "LONG" if score_long > score_short else "SHORT"

    total = score_long + score_short
    if total <= 0:
        confidence = 0.0
    else:
        dominant = max(score_long, score_short)
        confidence = min(100.0, (dominant / total) * 100.0)
        if directional:
            confidence = min(100.0, confidence * 0.6 + (dominant / len(directional)) * 0.4)
        if conflicts:
            confidence = max(0.0, confidence - st.conflict_penalty * len(conflicts))

    agreeing = 0
    if overall in ("LONG", "SHORT"):
        agreeing = sum(1 for s in directional if s.direction == overall)

    macro_sig = next((s for s in signals if s.strategy == "MACRO" and s.active), None)
    macro_direction: Direction | None = None
    macro_conflict = False
    if macro_sig and macro_sig.direction in ("LONG", "SHORT"):
        macro_direction = macro_sig.direction
        tech_overall = _dominant_technical_direction(signals, st)
        if tech_overall in ("LONG", "SHORT") and macro_direction != tech_overall:
            macro_conflict = True
            confidence = max(0.0, confidence - st.macro_conflict_penalty)
            if "MACRO" not in conflicts:
                conflicts = sorted(set(conflicts) | {"MACRO"})

    active_count = len(directional)
    agreement = f"{agreeing}/{active_count}" if active_count else "0/0"

    if not directional:
        summary = "No directional strategy signals — stand aside."
    elif conflicts:
        summary = f"Conflicting strategies ({', '.join(conflicts)}) — reduced confidence."
    elif overall == "NEUTRAL":
        summary = "Mixed or weak directional bias — monitor only."
    elif agreeing >= st.min_agreeing_for_strong and confidence >= st.min_confidence_strong:
        summary = f"Strong {overall} confluence ({agreement} strategies agree)."
    elif confidence >= st.min_confidence_setup:
        summary = f"Actionable {overall} setup forming ({agreement} agree)."
    else:
        summary = f"Early {overall} bias — wait for more agreement."

    if macro_conflict:
        summary = f"Macro vs technical conflict — wait for confirmation. {summary}"

    return ConfluenceResult(
        overall_direction=overall,
        confidence=confidence,
        agreement=agreement,
        agreeing_count=agreeing,
        active_count=active_count,
        conflicting_strategies=conflicts,
        strongest_strategy=strongest[0] or "—",
        components=components,
        summary=summary,
        score_long=score_long,
        score_short=score_short,
        macro_conflict=macro_conflict,
        macro_direction=macro_direction,
    )


def compute_confluence_from_ea(ea: dict[str, Any], cfg: ConfluenceConfig | None = None) -> dict[str, Any]:
    """Normalize EA payload and return confluence result dict."""
    st = cfg or ConfluenceConfig()
    signals = collect_confluence_signals(ea, st)
    result = compute_confluence(signals, st)
    return {
        "success": True,
        "confluence_enabled": st.enabled,
        "signals_count": len(signals),
        **result.to_dict(),
    }


def confluence_config_from_settings() -> ConfluenceConfig:
    """Build ConfluenceConfig from application settings."""
    from app.config import get_settings

    s = get_settings()
    weights = dict(DEFAULT_STRATEGY_WEIGHTS)
    weights["MACRO"] = float(s.confluence_macro_weight)
    return ConfluenceConfig(
        enabled=bool(s.confluence_enabled),
        freshness_threshold_sec=float(s.confluence_freshness_threshold_sec),
        stale_weight_factor=float(s.confluence_stale_weight_factor),
        min_agreeing_for_strong=int(s.confluence_min_agreeing_strong),
        min_confidence_strong=float(s.confluence_min_confidence_strong),
        min_confidence_setup=float(s.confluence_min_confidence_setup),
        conflict_penalty=float(s.confluence_conflict_penalty),
        macro_enabled=bool(s.market_news_enabled),
        macro_conflict_penalty=float(s.confluence_conflict_penalty) * 0.67,
        strategy_weights=weights,
    )


def verdict_from_confluence(
    conf: ConfluenceResult,
    *,
    blocks: list[str],
    cfg: ConfluenceConfig | None = None,
) -> tuple[str, str, str]:
    """Map confluence result to master verdict label, tone, summary."""
    st = cfg or ConfluenceConfig()
    if blocks:
        if conf.confidence >= st.min_confidence_setup:
            return "WATCH", "warn", conf.summary + " Caution: " + "; ".join(blocks[:2]) + "."
        return "NO TRADE", "muted", conf.summary + " Blocked: " + "; ".join(blocks[:2]) + "."

    if conf.macro_conflict and conf.agreeing_count < st.min_agreeing_for_strong:
        return "WATCH", "warn", conf.summary

    if (
        conf.overall_direction in ("LONG", "SHORT")
        and conf.agreeing_count >= st.min_agreeing_for_strong
        and conf.confidence >= st.min_confidence_strong
        and not conf.conflicting_strategies
    ):
        return "STRONG", "ok", conf.summary
    if (
        conf.confidence >= st.min_confidence_setup
        and conf.agreeing_count >= 1
        and conf.overall_direction in ("LONG", "SHORT")
    ):
        return "SETUP", "ok", conf.summary
    if conf.active_count > 0 or conf.confidence >= 30.0:
        return "WATCH", "warn", conf.summary
    return "NO TRADE", "muted", conf.summary
