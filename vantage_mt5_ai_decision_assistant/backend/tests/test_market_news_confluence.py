"""Step 8 — macro signal confluence integration tests."""
from app.analysis.confluence import (
    ConfluenceConfig,
    collect_confluence_signals,
    compute_confluence,
    normalize_ea_signals,
    verdict_from_confluence,
)
from app.analysis.confluence.types import ConfluenceResult, StrategySignal
from app.market_news.confluence_signal import normalize_macro_signal


def _macro_status(direction: str, confidence: float, *, tech: str = "BULLISH", alignment: str = "CONFLICT"):
    return {
        "macro_bias": {"direction": direction, "confidence": confidence, "horizon": "MEDIUM_TERM"},
        "technical_alignment": {
            "status": alignment,
            "recommendation": "WAIT" if alignment == "CONFLICT" else "CONFIRM",
            "reason": f"Macro {direction.lower()} vs technical {tech.lower()} momentum",
            "technical_direction": tech,
            "macro_direction": direction,
        },
        "drivers": ["Test macro driver"],
        "event_risk": {"blocked": False, "message": ""},
    }


def test_normalize_macro_signal_maps_bearish_to_short():
    cfg = ConfluenceConfig(macro_enabled=True)
    ea = {"symbol": "USDJPY", "connected": True}
    sig = normalize_macro_signal(
        ea,
        cfg,
        macro_status=_macro_status("BEARISH", 78.0),
    )
    assert sig is not None
    assert sig.strategy == "MACRO"
    assert sig.direction == "SHORT"
    assert sig.confidence == 78.0
    assert sig.weight == 0.35


def test_collect_confluence_signals_appends_macro(monkeypatch):
    monkeypatch.setenv("MARKET_NEWS_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    cfg = ConfluenceConfig(macro_enabled=True, strategy_weights={"MACRO": 0.35, "ICT": 1.0})
    ea = {
        "symbol": "USDJPY",
        "connected": True,
        "ict": {"valid": True, "decision": "BUY", "confidence_score": 85, "setup_state": "TRIGGERED"},
    }

    from app.market_news import confluence_signal as cs

    original = cs.normalize_macro_signal

    def _stub(ea_in, cfg_in, *, macro_status=None):
        return original(ea_in, cfg_in, macro_status=_macro_status("BEARISH", 80.0))

    monkeypatch.setattr(cs, "normalize_macro_signal", _stub)
    signals = collect_confluence_signals(ea, cfg)
    get_settings.cache_clear()
    assert any(s.strategy == "MACRO" for s in signals)


def test_macro_conflict_flags_and_penalizes_confidence():
    cfg = ConfluenceConfig(conflict_penalty=18.0, macro_conflict_penalty=12.0, min_agreeing_for_strong=2)
    signals = [
        StrategySignal(strategy="ICT", direction="LONG", confidence=85, status="TRIGGERED", weight=1.0),
        StrategySignal(strategy="AMD_IFVG", direction="LONG", confidence=80, status="ACTIVE", weight=0.95),
        StrategySignal(strategy="MACRO", direction="SHORT", confidence=78, status="CONFLICT", weight=0.35),
    ]
    result = compute_confluence(signals, cfg)
    assert result.macro_conflict is True
    assert result.macro_direction == "SHORT"
    assert "MACRO" in result.conflicting_strategies
    assert "Macro vs technical conflict" in result.summary


def test_verdict_watch_on_macro_conflict_without_strong_agreement():
    cfg = ConfluenceConfig(min_agreeing_for_strong=2, min_confidence_strong=78.0, min_confidence_setup=62.0)
    conf = ConfluenceResult(
        overall_direction="LONG",
        confidence=70.0,
        agreement="1/2",
        agreeing_count=1,
        active_count=2,
        conflicting_strategies=["MACRO"],
        strongest_strategy="ICT",
        components={},
        summary="Macro vs technical conflict — wait for confirmation. Actionable LONG setup forming (1/2 agree).",
        macro_conflict=True,
        macro_direction="SHORT",
    )
    verdict, tone, _ = verdict_from_confluence(conf, blocks=[], cfg=cfg)
    assert verdict == "WATCH"
    assert tone == "warn"


def test_macro_disabled_when_market_news_off(monkeypatch):
    monkeypatch.setenv("MARKET_NEWS_ENABLED", "false")
    from app.config import get_settings

    get_settings.cache_clear()
    cfg = ConfluenceConfig(macro_enabled=False)
    sig = normalize_macro_signal(
        {"symbol": "USDJPY"},
        cfg,
        macro_status=_macro_status("BEARISH", 80.0),
    )
    get_settings.cache_clear()
    assert sig is None


def test_technical_signals_unchanged_without_macro():
    ea = {
        "connected": True,
        "ict": {"valid": True, "decision": "SELL", "confidence_score": 85, "setup_state": "TRIGGERED"},
    }
    cfg = ConfluenceConfig(macro_enabled=False)
    assert len(normalize_ea_signals(ea, cfg)) == len(collect_confluence_signals(ea, cfg))
