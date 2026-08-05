"""AMD + iFVG status API tests."""
from fastapi.testclient import TestClient

from app.main import app
from app.monitor_state import monitor_store

SAMPLE_AMD_IFVG = {
    "module": "amd_ifvg",
    "version": "1.0",
    "valid": True,
    "gold_symbol_valid": True,
    "decision": "WAIT",
    "setup_state": "WAITING_FOR_RETRACE",
    "confidence": 78.5,
    "amd_phase": "DISTRIBUTION",
    "reasoning": ["Buy-side sweep above accumulation range."],
}


def test_amd_ifvg_status_passthrough():
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "amd_ifvg": SAMPLE_AMD_IFVG})
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/amd-ifvg/status").json()
    assert body["amd_ifvg_supported"] is True
    assert body["amd_ifvg"]["decision"] == "WAIT"


def test_amd_ifvg_analyze_endpoint():
    candles = [
        {"time": i, "open": 2650.0, "high": 2651.0, "low": 2649.0, "close": 2650.2}
        for i in range(30)
    ]
    r = TestClient(app).post(
        "/api/v1/amd-ifvg/analyze",
        json={"symbol": "XAUUSD", "candles": {"M15": candles, "M5": candles}},
    )
    assert r.status_code == 200
    assert "decision" in r.json()
