"""Confluence engine tests."""
from app.analysis.confluence import (
    ConfluenceConfig,
    compute_confluence,
    compute_confluence_from_ea,
    normalize_ea_signals,
    verdict_from_confluence,
)
from app.analysis.master_verdict import build_master_verdict


def _sig(strategy: str, direction: str, confidence: float, **kwargs):
    from app.analysis.confluence.types import StrategySignal

    return StrategySignal(
        strategy=strategy,
        direction=direction,
        confidence=confidence,
        status=kwargs.get("status", "ACTIVE"),
        weight=kwargs.get("weight", 1.0),
    )


def test_agreeing_short_signals():
    cfg = ConfluenceConfig(min_agreeing_for_strong=2, min_confidence_strong=70.0)
    signals = [
        _sig("ICT", "SHORT", 85),
        _sig("AMD_IFVG", "SHORT", 80),
        _sig("BOX_THEORY", "SHORT", 75),
    ]
    r = compute_confluence(signals, cfg)
    assert r.overall_direction == "SHORT"
    assert r.agreeing_count == 3
    assert r.confidence >= 70
    assert not r.conflicting_strategies


def test_conflicting_strategies_reduce_confidence():
    cfg = ConfluenceConfig(conflict_penalty=20.0)
    signals = [
        _sig("ICT", "SHORT", 85),
        _sig("SWING", "LONG", 90),
    ]
    r = compute_confluence(signals, cfg)
    assert "ICT" in r.conflicting_strategies
    assert "SWING" in r.conflicting_strategies
    assert r.conflicting_strategies


def test_normalize_ea_includes_ict():
    ea = {
        "connected": True,
        "new_entry_decision": "WAIT",
        "ict": {
            "valid": True,
            "analysis_active": True,
            "decision": "SELL",
            "confidence_score": 82,
            "setup_state": "ENTRY_ZONE_ACTIVE",
            "reasons": ["Bearish MSS after sweep"],
        },
        "amd_ifvg": {
            "valid": True,
            "analysis_active": True,
            "decision": "SELL",
            "confidence": 78,
            "setup_state": "WAITING_FOR_RETRACE",
        },
    }
    signals = normalize_ea_signals(ea)
    names = {s.strategy for s in signals}
    assert "ICT" in names
    assert "AMD_IFVG" in names
    shorts = [s for s in signals if s.direction == "SHORT"]
    assert len(shorts) >= 2


def test_compute_confluence_from_ea():
    ea = {
        "connected": True,
        "ict": {"valid": True, "decision": "BUY", "confidence_score": 88, "setup_state": "TRIGGERED"},
        "box_theory": {"valid": True, "signal": "BUY", "confidence_score": 76, "box_status": "VALID"},
    }
    out = compute_confluence_from_ea(ea)
    assert out["success"] is True
    assert out["overall_direction"] == "LONG"
    assert out["agreeing_count"] >= 2


def test_verdict_from_confluence_strong():
    from app.analysis.confluence.types import ConfluenceResult

    cfg = ConfluenceConfig(min_agreeing_for_strong=2, min_confidence_strong=75.0)
    conf = ConfluenceResult(
        overall_direction="SHORT",
        confidence=82.0,
        agreement="2/2",
        agreeing_count=2,
        active_count=2,
        conflicting_strategies=[],
        strongest_strategy="ICT",
        components={},
        summary="Strong SHORT confluence.",
    )
    verdict, tone, _ = verdict_from_confluence(conf, blocks=[], cfg=cfg)
    assert verdict == "STRONG"
    assert tone == "ok"


def test_master_verdict_ict_chip():
    mv = build_master_verdict(
        {
            "connected": True,
            "new_entry_decision": "WAIT",
            "ict": {
                "valid": True,
                "analysis_active": True,
                "decision": "WAIT",
                "confidence_score": 68,
                "setup_state": "MSS_CONFIRMED",
            },
        }
    )
    names = [m["name"] for m in mv["modules"]]
    assert "ICT" in names


def test_master_verdict_h4_m15_chip():
    mv = build_master_verdict(
        {
            "connected": True,
            "h4_m15_fvg": {
                "valid": True,
                "decision": "ENTRY_READY",
                "primary": {
                    "decision": "ENTRY_READY",
                    "state": "ENTRY_READY",
                    "score": 78.0,
                },
            },
        }
    )
    names = [m["name"] for m in mv["modules"]]
    assert "H4→M15" in names


def test_master_verdict_confluence_mode(monkeypatch):
    monkeypatch.setenv("CONFLUENCE_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()
    mv = build_master_verdict(
        {
            "connected": True,
            "new_entry_decision": "WAIT",
            "ict": {"valid": True, "decision": "SELL", "confidence_score": 85, "setup_state": "TRIGGERED"},
            "amd_ifvg": {"valid": True, "analysis_active": True, "decision": "SELL", "confidence": 80},
            "box_theory": {"valid": True, "signal": "SELL", "confidence_score": 78, "box_status": "VALID"},
        }
    )
    get_settings.cache_clear()
    assert "confluence" in mv
    assert mv["confluence"]["overall_direction"] == "SHORT"
    assert mv["side"] == "SELL"
    assert mv["verdict"] in ("STRONG", "SETUP", "WATCH")
