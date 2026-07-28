"""Pullback Probability Analyzer — heartbeat passthrough + status API."""
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.monitor_state import monitor_store


SAMPLE_PULLBACK = {
    "version": "1.0",
    "advisory_only": True,
    "valid": True,
    "dominant_direction": 1,
    "dominant_trend": "Moderate Bull",
    "pullback_probability": 62.0,
    "continuation_probability": 18.0,
    "consolidation_probability": 12.0,
    "reversal_probability": 8.0,
    "extension_score": 71.0,
    "pullback_quality": 55.0,
    "trend_strength": 64.0,
    "market_state": "DO NOT CHASE – MARKET EXTENDED",
    "explanation": "Price extended above M15 EMA; wait for pullback.",
    "short_reason": "DO NOT CHASE – MARKET EXTENDED",
    "nearest_support": 3300.0,
    "nearest_resistance": 3350.0,
    "pullback_target_low": 3310.0,
    "pullback_target_high": 3320.0,
    "invalidation": 3360.0,
    "reasons_positive": "Extreme extension raises pullback;",
    "reasons_negative": "No HTF CHoCH;",
    "session": "London",
}


def test_pullback_status_offline_empty():
    monitor_store.select_symbol("ZZPULLBACKOFF")
    client = TestClient(app)
    r = client.get("/api/v1/pullback/status")
    assert r.status_code == 200
    body = r.json()
    assert body["advisory_only"] is True
    assert body["ea_online"] is False
    assert body["pullback_supported"] is False
    assert body["pullback"] is None


def test_pullback_status_unsupported_when_missing():
    monitor_store.record_heartbeat(
        {
            "symbol": "PBUNSUPPORTED",
            "bid": 1.1,
            "ask": 1.2,
            "digits": 5,
        }
    )
    monitor_store.select_symbol("PBUNSUPPORTED")
    client = TestClient(app)
    body = client.get("/api/v1/pullback/status").json()
    assert body["ea_online"] is True
    assert body["pullback_supported"] is False
    assert body["pullback"] is None


def test_pullback_status_passthrough_from_heartbeat():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 3325.5,
            "ask": 3325.8,
            "digits": 2,
            "pullback": SAMPLE_PULLBACK,
        }
    )
    monitor_store.select_symbol("XAUUSD")
    client = TestClient(app)
    r = client.get("/api/v1/pullback/status")
    assert r.status_code == 200
    body = r.json()
    assert body["ea_online"] is True
    assert body["pullback_supported"] is True
    assert body["symbol"] == "XAUUSD"
    assert body["pullback"]["pullback_probability"] == 62.0
    assert body["pullback"]["market_state"] == "DO NOT CHASE – MARKET EXTENDED"
    assert "analyzer" in body["links"]


def test_pullback_page_served():
    client = TestClient(app)
    r = client.get("/pullback")
    assert r.status_code == 200
    assert "Pullback Probability Desk" in r.text


def test_heartbeat_accepts_pullback_field():
    token = get_settings().local_api_token
    client = TestClient(app)
    r = client.post(
        "/api/v1/heartbeat",
        json={
            "symbol": "XAUUSD",
            "bid": 2000.0,
            "ask": 2000.2,
            "digits": 2,
            "pullback": SAMPLE_PULLBACK,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    monitor_store.select_symbol("XAUUSD")
    st = client.get("/api/v1/pullback/status").json()
    assert st["pullback_supported"] is True
    assert st["pullback"]["continuation_probability"] == 18.0
