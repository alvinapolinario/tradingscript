"""Market State Engine v2 — API passthrough tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.monitor_state import monitor_store

client = TestClient(app)

SAMPLE_MSE = {
    "module": "market_state",
    "version": "2.0",
    "valid": True,
    "gold_symbol_valid": True,
    "symbol": "XAUUSD",
    "status_line": "Retesting | Score 72",
    "market_context": "Trending",
    "context_reason": "ADX expansion on H1",
    "bos_label": "Confirmed Bullish BOS",
    "bos_reason": "Close above swing high",
    "choch_label": "Waiting",
    "horizontal_breakout": "Confirmed",
    "trendline_breakout": "Retesting",
    "retest_status": "Retesting",
    "retest_reason": "Within ATR tolerance",
    "rbs_status": "Waiting Retest",
    "liquidity_status": "Potential Sweep",
    "confidence_score": 72.0,
    "institutional_probability": 88.0,
    "ml_trend_continuation": 85.0,
    "ml_failed_breakout": 10.0,
    "ml_deep_pullback": 5.0,
    "ml_distribution": "Trend Continuation 85% | Failed Breakout 10%",
    "signal_lifecycle": "Retesting",
    "score_breakdown": "BOS confirmed +20; Retest active +15;",
    "timeline": '[{"t":1710000000,"e":"Bullish BOS Confirmed","d":"Close above swing high"}]',
    "what_is_happening": "Price retesting broken resistance",
    "what_is_next": "Confirm RBS flip or fail retest",
    "missing_confirmations": "RBS confirmed flip",
    "recommendation": "Wait for retest confirmation — advisory only",
    "engine_phase": 2,
}


def test_market_state_status_offline_empty():
    monitor_store.select_symbol("ZZMSEOFF")
    r = client.get("/api/v1/market-state/status")
    assert r.status_code == 200
    body = r.json()
    assert body["market_state_engine_supported"] is False
    assert body["market_state_engine"] is None


def test_market_state_status_passthrough():
    monitor_store.record_heartbeat(
        {"symbol": "XAUUSD", "bid": 4040.0, "ask": 4040.2, "digits": 2, "market_state_engine": SAMPLE_MSE}
    )
    monitor_store.select_symbol("XAUUSD")
    r = client.get("/api/v1/market-state/status")
    body = r.json()
    assert body["market_state_engine_supported"] is True
    assert body["market_state_engine"]["signal_lifecycle"] == "Retesting"
    assert body["market_state_engine"]["confidence_score"] == 72.0
    assert "market_state" in body["links"]


def test_market_state_disabled_blob():
    monitor_store.record_heartbeat(
        {
            "symbol": "BTCUSD",
            "bid": 90000.0,
            "market_state_engine": {
                "valid": True,
                "gold_symbol_valid": False,
                "disable_reason": "Market State Engine v2 is disabled. This module supports XAUUSD/Gold only.",
            },
        }
    )
    monitor_store.select_symbol("BTCUSD")
    body = client.get("/api/v1/market-state/status").json()
    assert body["market_state_engine"]["gold_symbol_valid"] is False
    assert "XAUUSD/Gold only" in body["market_state_engine"]["disable_reason"]


def test_market_state_page_served():
    r = client.get("/market-state")
    assert r.status_code == 200
    assert "Market State Engine" in r.text
