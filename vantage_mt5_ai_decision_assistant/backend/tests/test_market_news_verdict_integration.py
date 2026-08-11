"""Step 9 — master verdict, analyzer, and desk gate integration tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.analysis.master_verdict import build_master_verdict
from app.market_news import store as news_store
from app.market_news.providers.registry import get_registry
from app.market_news.verdict_integration import (
    analyzer_macro_section,
    apply_macro_verdict_rules,
    build_news_gate,
    macro_module_chip,
)
from app.strategy_desk import STRATEGY_SPEC, evaluate_gates


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_registry.cache_clear()
    from app.config import get_settings

    get_settings.cache_clear()
    return db


def _macro_ctx(*, direction="BEARISH", confidence=78.0, alignment="CONFLICT", blocked=False):
    return {
        "enabled": True,
        "macro_bias": {"direction": direction, "confidence": confidence, "horizon": "MEDIUM_TERM"},
        "technical_alignment": {
            "status": alignment,
            "recommendation": "WAIT" if alignment == "CONFLICT" else "CONFIRM",
            "reason": f"Macro {direction.lower()} vs technical bullish momentum",
            "macro_direction": direction,
            "technical_direction": "BULLISH",
        },
        "event_risk": {
            "blocked": blocked,
            "minutes_to_next_high_impact": 20 if blocked else 120,
            "next_event": {"event": "US CPI", "currency": "USD"},
            "message": "High-impact window active" if blocked else "",
        },
        "drivers": ["Test driver"],
        "upcoming_events": [],
    }


def test_macro_module_chip_conflict_tone():
    chip = macro_module_chip(_macro_ctx(alignment="CONFLICT"))
    assert chip is not None
    assert chip["name"] == "Macro"
    assert chip["tone"] == "warn"


def test_apply_macro_verdict_conflict_waits():
    ea = {"new_entry_decision": "WAIT", "ict": {"valid": True, "decision": "WAIT", "confidence_score": 60}}
    verdict, tone, summary = apply_macro_verdict_rules(
        "SETUP",
        "ok",
        "Actionable setup.",
        _macro_ctx(alignment="CONFLICT"),
        ea=ea,
    )
    assert verdict == "WATCH"
    assert tone == "warn"
    assert "Macro conflict" in summary


def test_apply_macro_verdict_aligned_validates_setup():
    ea = {
        "new_entry_decision": "BUY_ALLOWED",
        "ict": {"valid": True, "decision": "BUY", "confidence_score": 82},
    }
    verdict, tone, summary = apply_macro_verdict_rules(
        "SETUP",
        "ok",
        "Actionable setup.",
        _macro_ctx(alignment="ALIGNED", direction="BULLISH"),
        ea=ea,
    )
    assert verdict == "SETUP"
    assert "Macro aligned" in summary


def test_master_verdict_includes_macro_chip():
    mv = build_master_verdict(
        {
            "connected": True,
            "symbol": "USDJPY",
            "new_entry_decision": "WAIT",
            "ict": {"valid": True, "decision": "BUY", "confidence_score": 80, "setup_state": "TRIGGERED"},
        }
    )
    names = [m["name"] for m in mv["modules"]]
    assert "Macro" in names
    assert "macro_recommendation" in mv


def test_build_news_gate_uses_backend_event(tmp_market_news_db):
    from app.market_news.types import economic_event_from_dict

    now = datetime.now(timezone.utc)
    scheduled = (now + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    news_store.upsert_economic_event(
        economic_event_from_dict(
            {
                "external_event_id": "cpi-block",
                "currency": "USD",
                "event": "Core CPI m/m",
                "category": "CPI_INFLATION",
                "importance": "HIGH",
                "scheduled_at": scheduled,
                "status": "SCHEDULED",
            }
        )
    )
    gate = build_news_gate(
        symbol="XAUUSD",
        spec=STRATEGY_SPEC,
        st={"news_available": False, "news_blocked": False},
        ea={"symbol": "XAUUSD", "connected": True},
    )
    assert gate is not None
    assert gate["status"] == "fail"
    assert "Core CPI" in gate["detail"]


def test_analyzer_macro_section_enabled():
    section = analyzer_macro_section({"symbol": "USDJPY", "connected": True})
    assert section["enabled"] is True
    assert "macro_bias" in section
    assert "recommendation" in section


def test_strategy_desk_news_gate_backend(tmp_market_news_db):
    from app.market_news.types import economic_event_from_dict

    now = datetime.now(timezone.utc)
    scheduled = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    news_store.upsert_economic_event(
        economic_event_from_dict(
            {
                "external_event_id": "nfp-future",
                "currency": "USD",
                "event": "Nonfarm Payrolls",
                "category": "EMPLOYMENT",
                "importance": "HIGH",
                "scheduled_at": scheduled,
                "status": "SCHEDULED",
            }
        )
    )
    status = {
        "selected_symbol": "XAUUSD",
        "link_health": {"ea_online": True},
        "vantage_ea": {
            "connected": True,
            "symbol": "XAUUSD",
            "spread_points": 30,
            "strategy": {
                "h1_bias": "BULLISH",
                "m15_structure": "BULLISH",
                "h1_m15_aligned": True,
                "adx14": 24,
                "reward_risk_ratio": 2.0,
                "planned_equity_risk_pct": 0.5,
                "news_available": False,
                "news_blocked": False,
                "setup_age_m5": 1,
                "m5_closed_confirmed": True,
            },
        },
    }
    gates = evaluate_gates(status)
    news = next(g for g in gates if g["key"] == "news")
    assert news["status"] == "pass"
    assert "Nonfarm Payrolls" in news["detail"]
