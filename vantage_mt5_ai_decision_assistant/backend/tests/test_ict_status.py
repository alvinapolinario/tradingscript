"""ICT strategy API tests."""
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.monitor_state import monitor_store

SAMPLE_ICT = {
    "module": "ict",
    "version": "1.0",
    "valid": True,
    "gold_symbol_valid": True,
    "strategy": "ICT",
    "status": "WAITING_FOR_RETRACE",
    "setup_state": "WAITING_FOR_RETRACE",
    "decision": "WAIT",
    "confidence": 68,
    "confidence_score": 68,
    "setup_id": "ICT-XAUUSD-M15-1700038700-S",
    "htf_bias": {"direction": "BEARISH", "confidence": 72, "evidence": ["H1 bearish structure"]},
    "liquidity": {"sweep_detected": True, "type": "BUY_SIDE", "level": 4011.0},
}


def test_ict_status_passthrough():
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "ict": SAMPLE_ICT})
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/ict/status").json()
    assert body["ict_supported"] is True
    assert body["backend_engine_available"] is True
    assert "EURUSD, USDJPY" in body["caption"]
    assert body["ict"]["decision"] == "WAIT"


def test_heartbeat_accepts_ict_field():
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
            "ict": SAMPLE_ICT,
        },
    )
    assert r.status_code == 200
    monitor_store.select_symbol("XAUUSD")
    st = client.get("/api/v1/ict/status").json()
    assert st["ict_supported"] is True
    assert st["ict"]["setup_id"] == "ICT-XAUUSD-M15-1700038700-S"


def test_ict_strategy_summary_endpoint():
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "ict": SAMPLE_ICT})
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/strategies/ict/XAUUSD").json()
    assert body["success"] is True
    assert body["strategy"] == "ICT"
    assert body["decision"] == "WAIT"


def test_ict_status_normalizes_vantage_plus_symbol():
    monitor_store.record_heartbeat(
        {
            "symbol": "EURUSD+",
            "bid": 1.085,
            "ask": 1.0851,
            "digits": 5,
            "ict": {
                "valid": True,
                "gold_symbol_valid": False,
                "symbol": "EURUSD+",
                "disable_reason": "ICT Strategy Engine is disabled. Supported pairs: XAUUSD, EURUSD, USDJPY.",
                "decision": "WAIT",
            },
        }
    )
    monitor_store.select_symbol("EURUSD")
    body = TestClient(app).get("/api/v1/ict/status").json()
    assert body["ict"]["gold_symbol_valid"] is True
    assert body["ict"]["base_symbol"] == "EURUSD"


def test_ict_analyze_endpoint():
    candles = []
    base = 4000.0
    t = 1_700_000_000
    for i in range(60):
        candles.append(
            {
                "time": t + i * 900,
                "open": base,
                "high": base + 8,
                "low": base - 2,
                "close": base + 1,
            }
        )
    candles.append(
        {"time": t + 60 * 900, "open": base + 8, "high": base + 12.5, "low": base + 7, "close": base + 9.5}
    )
    r = TestClient(app).post(
        "/api/v1/ict/analyze",
        json={
            "symbol": "XAUUSD",
            "timeframe": "M15",
            "candles": {"M15": candles, "M5": candles[-10:]},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["strategy"] == "ICT"
    assert "score_components" in data
    assert "setup_id" in data


def test_ict_analyze_alias_route():
    candles = [{"time": 1000 + i, "open": 100, "high": 101, "low": 99, "close": 100} for i in range(65)]
    r = TestClient(app).post(
        "/api/v1/strategy/ict/analyze",
        json={"symbol": "XAUUSD", "candles": {"M15": candles}},
    )
    assert r.status_code == 200
    assert r.json()["strategy"] == "ICT"


def test_ict_history_after_analyze():
    from app.analysis.ict.state_store import clear_store

    clear_store()
    candles = [{"time": 1000 + i, "open": 100, "high": 101, "low": 99, "close": 100} for i in range(65)]
    client = TestClient(app)
    client.post("/api/v1/ict/analyze", json={"symbol": "XAUUSD", "candles": {"M15": candles}})
    hist = client.get("/api/v1/strategies/ict/XAUUSD/history").json()
    assert hist["success"] is True
    assert hist["count"] >= 1
