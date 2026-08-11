"""Liquidity Grab Monitor — status API + gold gate tests."""
from fastapi.testclient import TestClient

from app.analysis.gold_symbol_validator import is_approved_gold_symbol
from app.analysis.liquidity_grab_logic import (
    LiquidityGrabScoreInput,
    classify_mss_cap_without_mss,
    score_liquidity_grab,
)
from app.main import app
from app.monitor_state import monitor_store

SAMPLE_LIQUIDITY_GRAB = {
    "module": "liquidity_grab",
    "version": "1.0",
    "valid": True,
    "gold_symbol_valid": True,
    "engine_enabled": True,
    "analysis_active": True,
    "symbol": "XAUUSD",
    "base_symbol": "XAUUSD",
    "status_line": "LIQUIDITY_GRAB_CONFIRMED",
    "disable_reason": "",
    "detection_tf": "PERIOD_M5",
    "confirmation_tf": "PERIOD_M5",
    "higher_tf": "PERIOD_H1",
    "direction": "BUY_SIDE_GRAB_BEARISH_REVERSAL",
    "status": "LIQUIDITY_GRAB_CONFIRMED",
    "machine_state": "CONFIRMED",
    "confidence_score": 82.0,
    "liquidity_level_id": "LG-ASIAN_HIGH-4043.80",
    "liquidity_level_type": "ASIAN_HIGH",
    "liquidity_level_price": 4043.80,
    "sweep_price": 4044.25,
    "sweep_distance": 0.45,
    "sweep_distance_atr": 0.107,
    "rejection_close_price": 4043.50,
    "wick_ratio": 0.48,
    "displacement_detected": True,
    "displacement_strength": 0.62,
    "mss_detected": True,
    "mss_type": "INTERNAL",
    "mss_level": 4039.90,
    "fvg_detected": True,
    "volume_ratio": 1.42,
    "session_name": "London–New York Overlap",
    "higher_timeframe_bias": "BEARISH",
    "ema_alignment": "Bearish stack",
    "is_countertrend": False,
    "news_restricted": False,
    "spread_at_detection": 18.0,
    "candidate_start_time": 1720000000,
    "confirmation_time": 1720000300,
    "expiry_time": 1720000600,
    "invalidation_reason": "",
    "evidence": "Sweep 0.45 beyond ASIAN_HIGH;Rejection detected;MSS break at 4039.90",
    "warnings": "",
    "nearest_opposing_liquidity": 4035.0,
    "nearest_opposing_label": "SWING_LOW",
    "invalidation_level": 4039.90,
    "recommendation": "CONFIRMED STRUCTURAL EVENT",
    "technical_narrative": "Status LIQUIDITY_GRAB_CONFIRMED | BUY_SIDE_GRAB_BEARISH_REVERSAL | Score 82",
    "action_guidance": "Conditions met — monitor invalidation level",
    "setup_age_bars": 3,
    "confirmation_countdown": 2,
    "last_alert": "",
    "last_alert_time": 0,
    "chart_objects_active": True,
    "eval_bar_m5": 1720000300,
    "engine_phase": 1,
}


def test_liquidity_grab_status_offline_empty():
    monitor_store.select_symbol("ZZLIQGRABOFF")
    client = TestClient(app)
    body = client.get("/api/v1/liquidity-grab/status").json()
    assert body["liquidity_grab_supported"] is False
    assert body["liquidity_grab"] is None


def test_liquidity_grab_status_passthrough():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 4043.0,
            "ask": 4043.2,
            "digits": 2,
            "liquidity_grab": SAMPLE_LIQUIDITY_GRAB,
        }
    )
    monitor_store.select_symbol("XAUUSD")
    client = TestClient(app)
    body = client.get("/api/v1/liquidity-grab/status").json()
    assert body["liquidity_grab_supported"] is True
    assert body["liquidity_grab"]["status"] == "LIQUIDITY_GRAB_CONFIRMED"
    assert body["liquidity_grab"]["confidence_score"] == 82.0
    assert body["liquidity_grab"]["mss_detected"] is True
    assert "liquidity_grab" in body["links"]


def test_liquidity_grab_eurusd_passthrough():
    sample = dict(SAMPLE_LIQUIDITY_GRAB)
    sample.update({"symbol": "EURUSD", "base_symbol": "EURUSD", "liquidity_level_price": 1.0850, "sweep_price": 1.0852})
    monitor_store.record_heartbeat(
        {
            "symbol": "EURUSD",
            "bid": 1.0850,
            "ask": 1.0851,
            "digits": 5,
            "liquidity_grab": sample,
        }
    )
    monitor_store.select_symbol("EURUSD")
    client = TestClient(app)
    body = client.get("/api/v1/liquidity-grab/status").json()
    assert body["liquidity_grab_supported"] is True
    assert body["liquidity_grab"]["gold_symbol_valid"] is True
    assert body["liquidity_grab"]["symbol"] == "EURUSD"


def test_liquidity_grab_disabled_blob():
    monitor_store.record_heartbeat(
        {
            "symbol": "BTCUSD",
            "bid": 90000.0,
            "ask": 90001.0,
            "digits": 2,
            "liquidity_grab": {
                "valid": True,
                "gold_symbol_valid": False,
                "disable_reason": "Liquidity Grab Monitor is disabled. Supported pairs: XAUUSD, EURUSD, USDJPY.",
            },
        }
    )
    monitor_store.select_symbol("BTCUSD")
    client = TestClient(app)
    body = client.get("/api/v1/liquidity-grab/status").json()
    assert body["liquidity_grab"]["gold_symbol_valid"] is False
    assert "Supported pairs" in body["liquidity_grab"]["disable_reason"]


def test_liquidity_grab_page_served():
    client = TestClient(app)
    r = client.get("/liquidity-grab")
    assert r.status_code == 200
    assert "LIQUIDITY GRAB" in r.text.upper()


def test_scoring_confirmed_buy_side_grab():
    inp = LiquidityGrabScoreInput(
        level_type="ASIAN_HIGH",
        close_back_inside=True,
        wick_ratio=0.48,
        displacement=True,
        mss=True,
        htf_aligned=True,
        session_boost=True,
    )
    score, status = score_liquidity_grab(inp)
    assert score >= 70
    assert status in ("LIQUIDITY_GRAB_CONFIRMED", "HIGH_CONFIDENCE_LIQUIDITY_GRAB")


def test_scoring_wick_without_mss_capped():
    assert classify_mss_cap_without_mss()


def test_scoring_genuine_breakout():
    inp = LiquidityGrabScoreInput(genuine_breakout=True)
    _, status = score_liquidity_grab(inp)
    assert status == "GENUINE_BREAKOUT"


def test_gold_alias_for_liquidity_grab():
    ok, base = is_approved_gold_symbol("XAUUSD.a")
    assert ok and base == "XAUUSD"
