"""Pattern Strategy, Strategy Scanner, Strategy Lab."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.monitor_state import monitor_store
from app.strategy_workspace import build_lab, build_patterns, build_scanner, sanitize_lab_overrides


def _ok_status(symbol="XAUUSD", connected=True):
    strategy = {
        "h1_bias": "BULLISH",
        "m15_structure": "BULLISH",
        "h1_m15_aligned": True,
        "adx14": 24.0,
        "atr14": 12.5,
        "reward_risk_ratio": 2.0,
        "planned_equity_risk_pct": 0.50,
        "max_spread_points": 50,
        "news_available": True,
        "news_blocked": False,
        "minutes_to_high_impact": 120,
        "setup_age_m5": 1,
        "m5_closed_confirmed": True,
        "ema_stack_ok": True,
        "m5_trigger": "BULLISH",
        "allowed_direction": "BUY",
    }
    return {
        "selected_symbol": symbol,
        "available_symbols": [symbol],
        "lab_overrides": {},
        "link_health": {
            "api_online": True,
            "ea_online": connected,
            "any_ea_online": connected,
            "overall": "CONNECTED" if connected else "WAITING_FOR_EA",
        },
        "vantage_ea": {
            "connected": connected,
            "seconds_since_seen": 2,
            "symbol": symbol,
            "spread_points": 20,
            "high_spread": False,
            "bid": 4100.0,
            "ask": 4100.3,
            "digits": 2,
            "strategy": strategy,
        },
    }


def test_patterns_catalog_active(_=None):
    out = build_patterns(_ok_status())
    assert out["total"] >= 8
    assert out["active_count"] >= 5
    assert any(i["id"] == "h1_m15_align" and i["active"] for i in out["items"])


def test_scanner_ranks_setup_ok():
    base = _ok_status("XAUUSD")
    pairs = [_ok_status("XAUUSD"), _ok_status("BTCUSD", connected=False)]
    pairs[1]["vantage_ea"]["strategy"]["h1_m15_aligned"] = False
    out = build_scanner(base, pairs)
    assert out["count"] == 2
    assert out["items"][0]["symbol"] == "XAUUSD"
    assert out["items"][0]["verdict"] == "SETUP_OK"


def test_lab_overrides_tighten_adx():
    st = _ok_status()
    st["vantage_ea"]["strategy"]["adx14"] = 22.0
    base = build_lab(st)
    assert base["verdict"]["verdict"] == "SETUP_OK"
    trial = build_lab(st, trial_overrides={"min_adx": 30})
    adx_gate = next(g for g in trial["gates"] if g["key"] == "adx")
    assert adx_gate["status"] == "fail"


def test_sanitize_lab_overrides():
    assert sanitize_lab_overrides({"min_adx": "25", "bogus": 1}) == {"min_adx": 25.0}


def test_lab_api_apply_reset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monitor_store.clear_lab_overrides()
    client = TestClient(app)
    r = client.post("/api/v1/lab/apply", json={"min_adx": 25, "risk_pct": 0.4})
    assert r.status_code == 200
    assert r.json()["session_overrides"]["min_adx"] == 25.0
    r2 = client.post("/api/v1/lab/reset")
    assert r2.status_code == 200
    assert r2.json()["session_overrides"] == {}


def test_patterns_api():
    client = TestClient(app)
    r = client.get("/api/v1/patterns/status")
    assert r.status_code == 200
    assert "items" in r.json()
