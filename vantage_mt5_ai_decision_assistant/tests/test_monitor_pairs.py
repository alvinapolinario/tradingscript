"""Multi-pair monitor selection (XAUUSD / BTCUSD)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings
from app.monitor_state import monitor_store

TOKEN = get_settings().local_api_token
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_monitor_pair_selector_and_isolation():
    client = TestClient(app)

    # Seed two live pairs
    assert client.post(
        "/api/v1/heartbeat",
        json={
            "symbol": "XAUUSD",
            "currency": "USD",
            "bid": 4100.0,
            "ask": 4100.5,
            "action": "WAIT",
            "new_entry_decision": "NO_NEW_TRADE",
            "risk_status": "LOW",
        },
        headers=AUTH,
    ).status_code == 200
    assert client.post(
        "/api/v1/heartbeat",
        json={
            "symbol": "BTCUSD",
            "currency": "USD",
            "bid": 65000.0,
            "ask": 65050.0,
            "action": "BUY_ZONE",
            "new_entry_decision": "ALLOW_NEW_TRADE",
            "risk_status": "MODERATE",
        },
        headers=AUTH,
    ).status_code == 200

    status = monitor_store.status()
    names = status["available_symbols"]
    assert "XAUUSD" in names and "BTCUSD" in names

    # Select BTCUSD
    r = client.post("/api/v1/monitor/select-symbol", json={"symbol": "btcusd"})
    assert r.status_code == 200
    body = r.json()
    assert body["selected_symbol"] == "BTCUSD"
    assert body["vantage_ea"]["symbol"] == "BTCUSD"
    assert body["vantage_ea"]["bid"] == 65000.0
    assert body["vantage_ea"]["action"] == "BUY_ZONE"

    # Select XAUUSD — BTC snapshot must not leak
    r2 = client.post("/api/v1/monitor/select-symbol", json={"symbol": "XAUUSD"})
    assert r2.status_code == 200
    gold = r2.json()["vantage_ea"]
    assert gold["symbol"] == "XAUUSD"
    assert gold["bid"] == 4100.0
    assert gold["action"] == "WAIT"

    html = client.get("/monitor").text
    assert 'id="pairSelect"' in html
    assert "BTCUSD" in html
