"""Signal Center clear API."""
from fastapi.testclient import TestClient

from app import signal_ledger as ledger
from app.main import app

client = TestClient(app)


def _ok_status(side_bias="BEARISH", symbol="XAUUSD"):
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
        "allowed_direction": "SELL" if side_bias == "BEARISH" else "BUY",
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
            "spread_points": 20,
            "high_spread": False,
            "bid": 3300.0,
            "ask": 3300.2,
            "digits": 2,
            "strategy": strategy,
        },
    }


def test_signals_page_has_clear_controls():
    r = client.get("/signals")
    assert r.status_code == 200
    assert "Clear decided" in r.text
    assert "Clear all" in r.text
    assert "/api/v1/signals/clear" in r.text


def test_clear_api_decided(tmp_path, monkeypatch):
    db = tmp_path / "signal_ledger.db"
    monkeypatch.setattr(ledger, "_DB_PATH", db)
    monkeypatch.setattr(ledger, "_DATA_DIR", tmp_path)
    ledger.init_db()
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    ledger.record_decision(accepted["id"], "IGNORE")
    r = client.post("/api/v1/signals/clear", json={"scope": "decided"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["deleted"] == 1
    assert ledger.list_signals() == []


def test_clear_api_invalid_scope():
    r = client.post("/api/v1/signals/clear", json={"scope": "nope"})
    assert r.status_code == 400
