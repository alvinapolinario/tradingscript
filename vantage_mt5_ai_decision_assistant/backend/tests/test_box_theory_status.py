"""Box Theory status API tests."""
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.monitor_state import monitor_store

SAMPLE_BOX = {
    "module": "box_theory",
    "version": "1.0",
    "valid": True,
    "gold_symbol_valid": True,
    "strategy": "BOX_THEORY",
    "signal": "WATCH",
    "box_status": "VALID",
    "confidence_score": 62,
    "box": {"high": 3400, "low": 3380, "mid": 3390, "height": 20, "upper_touches": 3, "lower_touches": 2},
}


def test_box_theory_status_passthrough():
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "box_theory": SAMPLE_BOX})
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/box-theory/status").json()
    assert body["box_theory_supported"] is True
    assert body["box_theory"]["signal"] == "WATCH"


def test_heartbeat_accepts_box_theory_field():
    token = get_settings().local_api_token
    client = TestClient(app)
    r = client.post(
        "/api/v1/heartbeat",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "symbol": "XAUUSD",
            "bid": 3400.0,
            "ask": 3400.2,
            "digits": 2,
            "box_theory": SAMPLE_BOX,
        },
    )
    assert r.status_code == 200
    monitor_store.select_symbol("XAUUSD")
    st = client.get("/api/v1/box-theory/status").json()
    assert st["box_theory_supported"] is True
    assert st["box_theory"]["signal"] == "WATCH"


def test_box_strategy_summary_endpoint():
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "box_theory": SAMPLE_BOX})
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/strategies/box/XAUUSD").json()
    assert body["success"] is True
    assert body["signal"] == "WATCH"


def test_box_theory_analyze_endpoint():
    candles = []
    hi, lo = 3400.0, 3380.0
    mid = (hi + lo) / 2
    for i in range(20):
        if i % 4 == 0:
            candles.append({"time": 1000 + i, "open": mid, "high": hi, "low": lo + 4, "close": hi - 0.5})
        elif i % 4 == 1:
            candles.append({"time": 1000 + i, "open": mid, "high": hi - 4, "low": lo, "close": lo + 0.5})
        else:
            candles.append({"time": 1000 + i, "open": mid, "high": hi - 2, "low": lo + 2, "close": mid})
    r = TestClient(app).post(
        "/api/v1/box-theory/analyze",
        json={"symbol": "XAUUSD", "candles": {"M15": candles, "M5": candles}},
    )
    assert r.status_code == 200
    assert r.json()["strategy"] == "BOX_THEORY"
