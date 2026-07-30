"""Swing Strategy Engine — API passthrough tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.monitor_state import monitor_store

client = TestClient(app)

SAMPLE_SWING = {
    "module": "swing_strategy",
    "version": "1.0",
    "valid": True,
    "gold_symbol_valid": True,
    "symbol": "XAUUSD",
    "trend": "Bullish",
    "market_structure": "HH-HL",
    "current_phase": "Pullback",
    "swing_direction": "Bullish",
    "trend_score": 92.0,
    "swing_score": 88.0,
    "momentum_score": 88.0,
    "smc_score": 95.0,
    "liquidity_score": 83.0,
    "breakout_score": 86.0,
    "confidence": 91.0,
    "signal": "STRONG SWING BUY",
    "entry_quality": "Excellent",
    "entry_zone": [4028.50, 4032.00],
    "stop_loss": 4016.80,
    "tp1": 4050.0,
    "tp2": 4068.0,
    "tp3": 4090.0,
    "risk_reward": "1:3.2",
    "reason": "Bullish BOS confirmed after liquidity sweep with healthy pullback.",
    "eval_bar_m5": 1710000000,
}


def test_swing_strategy_status_offline_empty():
    monitor_store.select_symbol("ZZSWINGOFF")
    body = client.get("/api/v1/swing-strategy/status").json()
    assert body["swing_strategy_supported"] is False
    assert body["swing_strategy"] is None


def test_swing_strategy_status_passthrough():
    monitor_store.record_heartbeat(
        {"symbol": "XAUUSD", "bid": 4040.0, "ask": 4040.2, "digits": 2, "swing_strategy": SAMPLE_SWING}
    )
    monitor_store.select_symbol("XAUUSD")
    body = client.get("/api/v1/swing-strategy/status").json()
    assert body["swing_strategy_supported"] is True
    assert body["swing_strategy"]["signal"] == "STRONG SWING BUY"
    assert body["swing_strategy"]["confidence"] == 91.0
    assert "swing_strategy" in body["links"]


def test_swing_strategy_page_served():
    r = client.get("/swing-strategy")
    assert r.status_code == 200
    assert "Swing Strategy Engine" in r.text
