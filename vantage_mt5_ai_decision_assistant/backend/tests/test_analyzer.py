"""Smart Analyzer status + Take/Ignore decisions."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import signal_ledger as ledger
from app.main import app


def _ok_status(side_bias="BULLISH", symbol="XAUUSD"):
    strategy = {
        "h1_bias": side_bias,
        "m15_structure": side_bias,
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
        "m5_trigger": side_bias,
        "allowed_direction": "BUY" if side_bias == "BULLISH" else "SELL",
    }
    return {
        "selected_symbol": symbol,
        "available_symbols": [symbol],
        "link_health": {
            "api_online": True,
            "ea_online": True,
            "any_ea_online": True,
            "overall": "CONNECTED",
        },
        "vantage_ea": {
            "connected": True,
            "seconds_since_seen": 2,
            "symbol": symbol,
            "company": "Vantage Markets (Pty) Ltd.",
            "spread_points": 20,
            "high_spread": False,
            "bid": 4100.0,
            "ask": 4100.3,
            "digits": 2,
            "market_state": "Transition",
            "strategy": strategy,
        },
    }


@pytest.fixture()
def tmp_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "signal_ledger.db"
    monkeypatch.setattr(ledger, "_DB_PATH", db)
    monkeypatch.setattr(ledger, "_DATA_DIR", tmp_path)
    ledger.init_db()
    return db


def test_analyzer_status_preview(tmp_ledger):
    st = ledger.build_analyzer_status(_ok_status(), mode="STANDARD")
    assert st["advisory_only"] is True
    assert st["decision_state"] == "AWAITING_YOUR_DECISION"
    assert st["active_signal"]["side"] == "BUY"
    assert st["active_signal"].get("preview") is True
    assert "Vantage" in st["broker"]
    assert st["votes"]["buy_points"] >= st["votes"]["sell_points"]


def test_record_take_decision(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    updated = ledger.record_decision(accepted["id"], "TAKE")
    assert updated["user_decision"] == "TAKE"
    assert updated["decided_utc"]
    st = ledger.build_analyzer_status(_ok_status())
    assert st["decision_state"] == "TAKEN"
    assert st["active_signal"]["id"] == accepted["id"]


def test_decision_api(tmp_ledger, monkeypatch):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    client = TestClient(app)
    r = client.post(f"/api/v1/signals/{accepted['id']}/decision", json={"decision": "IGNORE"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["signal"]["user_decision"] == "IGNORE"
    assert "no MT5 order" in body["caption"]


def test_invalid_decision_raises(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    with pytest.raises(ValueError):
        ledger.record_decision(accepted["id"], "BUY_NOW")
