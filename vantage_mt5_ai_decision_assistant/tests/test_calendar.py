"""PL calendar store/heartbeat smoke tests."""
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


def test_heartbeat_stores_pl_calendar():
    client = TestClient(app)
    payload = {
        "ea_version": "1.2.0",
        "symbol": "XAUUSD",
        "currency": "USD",
        "equity": 200.0,
        "floating_pl": 0.0,
        "pl_calendar": {
            "year": 2026,
            "month": 7,
            "equity_ref": 200.0,
            "currency": "USD",
            "month_pl": 12.5,
            "month_pct": 6.25,
            "month_deals": 4,
            "ok": True,
            "days": [
                {"d": 1, "pl": 5.0, "pct": 2.5, "deals": 1},
                {"d": 15, "pl": 7.5, "pct": 3.75, "deals": 3},
            ],
        },
    }
    r = client.post("/api/v1/heartbeat", json=payload, headers=AUTH)
    assert r.status_code == 200
    client.post("/api/v1/monitor/select-symbol", json={"symbol": "XAUUSD"})
    status = monitor_store.status()
    cal = status["vantage_ea"]["pl_calendar"]
    assert cal["month"] == 7
    assert cal["days"][0]["pct"] == 2.5
    assert "Trading History Calendar" in client.get("/monitor").text


def test_calendar_month_navigation_api():
    client = TestClient(app)
    # Seed current month via heartbeat
    client.post(
        "/api/v1/heartbeat",
        json={
            "symbol": "XAUUSD",
            "currency": "USD",
            "server_year": 2026,
            "server_month": 7,
            "pl_calendar": {
                "year": 2026,
                "month": 7,
                "ok": True,
                "equity_ref": 200,
                "currency": "USD",
                "month_pl": 1,
                "month_pct": 0.5,
                "month_deals": 1,
                "days": [{"d": 10, "pl": 1, "pct": 0.5, "deals": 1}],
            },
        },
        headers=AUTH,
    )
    r = client.post("/api/v1/monitor/calendar-month", json={"year": 2026, "month": 6})
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026 and body["month"] == 6
    assert body["pending"] is True  # June not cached yet
    hb = client.post(
        "/api/v1/heartbeat",
        json={"symbol": "XAUUSD", "currency": "USD"},
        headers=AUTH,
    )
    assert hb.status_code == 200
    assert hb.json()["calendar_year"] == 2026
    assert hb.json()["calendar_month"] == 6


def test_heartbeat_stores_trade_stats():
    client = TestClient(app)
    payload = {
        "ea_version": "1.2.0",
        "symbol": "XAUUSD",
        "currency": "USD",
        "equity": 200.0,
        "trade_stats": {
            "ok": True,
            "currency": "USD",
            "total_trades": 10,
            "wins": 6,
            "losses": 4,
            "breakeven": 0,
            "win_rate_pct": 60.0,
            "net_profit": 25.0,
            "profit_factor": 1.8,
            "max_drawdown": 12.0,
            "max_drawdown_pct": 6.0,
            "gross_profit": 45.0,
            "gross_loss": -20.0,
            "avg_win": 7.5,
            "avg_loss": -5.0,
            "lookback_days": 0,
            "symbol_filter": "",
        },
    }
    r = client.post("/api/v1/heartbeat", json=payload, headers=AUTH)
    assert r.status_code == 200
    client.post("/api/v1/monitor/select-symbol", json={"symbol": "XAUUSD"})
    st = monitor_store.status()["vantage_ea"]["trade_stats"]
    assert st["wins"] == 6
    assert st["win_rate_pct"] == 60.0
    assert "Account Performance" in client.get("/monitor").text
