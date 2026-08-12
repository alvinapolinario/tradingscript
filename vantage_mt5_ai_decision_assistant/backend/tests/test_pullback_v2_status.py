"""Pullback Desk V2 — heartbeat passthrough + status API."""
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.monitor_state import monitor_store


SAMPLE_PULLBACK_V2 = {
    "version": "pullback_v2",
    "milestone": 7,
    "experimental": True,
    "calibrated": False,
    "valid": True,
    "symbol": "XAUUSD",
    "dominant_direction": 1,
    "dominant_trend": "Moderate Bullish",
    "trend_strength": 64.0,
    "extension_score": 78.0,
    "displacement_score": 86.0,
    "entry_location_score": 28.0,
    "pullback_score": 68.0,
    "immediate_continuation_score": 51.0,
    "continuation_after_pullback_score": 72.0,
    "reversal_risk_score": 12.0,
    "expected_pullback_atr": 0.85,
    "expected_depth": "MODERATE",
    "momentum_state": "EXTENDED",
    "rsi_level": 72.5,
    "rsi_slope": -1.2,
    "premium_discount_location": "Deep Premium",
    "range_position_pct": 82.0,
    "prediction_horizon": {"timeframe": "PERIOD_M15", "bars": 6, "minutes": 90},
    "pullback_event_definition": {
        "threshold_atr": 0.5,
        "description": "Experimental pullback event definition",
    },
    "displacement": {
        "body": 75.0,
        "range": 68.0,
        "persistence": 50.0,
        "close_quality": 82.0,
        "ema_accel": 55.0,
        "bos": 100.0,
        "fvg": 0.0,
    },
    "momentum": {
        "state": "EXTENDED",
        "rsi_level": 72.5,
        "rsi_slope": -1.2,
    },
    "dealing_range": {
        "low": 3310.0,
        "high": 3360.0,
        "position_pct": 82.0,
        "location": "Deep Premium",
    },
    "liquidity": {
        "draw": "buy_side",
        "state": "approaching",
        "target_price": 3360.0,
        "target_label": "PDH",
        "distance_atr": 0.32,
        "from_liquidity_grab": True,
    },
    "liquidity_draw": "buy_side",
    "liquidity_state": "approaching",
    "liquidity_distance_atr": 0.32,
    "liquidity_from_grab_module": True,
    "poi": {
        "primary_type": "Fair Value Gap",
        "primary_dir": "Bullish",
        "status": "fresh",
        "upper": 3338.0,
        "lower": 3332.0,
        "mid": 3335.0,
        "quality": 72.0,
        "mitigation_pct": 0.0,
        "distance_atr": 0.45,
        "pullback_target_score": 78.0,
        "confluence_score": 68.0,
        "fvg_count": 2,
        "ob_count": 1,
        "price_inside": False,
        "price_approaching": True,
        "from_gold_smc": True,
    },
    "poi_primary_type": "Fair Value Gap",
    "poi_pullback_target_score": 78.0,
    "ote": {
        "valid": True,
        "ote_low": 3320.0,
        "ote_mid": 3328.0,
        "ote_high": 3335.0,
        "price_in_ote": False,
        "poi_overlaps_ote": True,
        "alignment_score": 88.0,
        "from_gold_smc": True,
    },
    "depth": {
        "target_low": 3318.0,
        "target_mid": 3328.0,
        "target_high": 3336.0,
        "expected_pullback_atr": 0.72,
        "expected_depth": "MODERATE",
        "fib_retrace_pct": 64.0,
        "source": "ote+poi",
    },
    "depth_source": "ote+poi",
    "ote_valid": True,
    "price_in_ote": False,
    "poi_overlaps_ote": True,
    "ote_alignment_score": 88.0,
    "reference_close": 3335.0,
    "atr_m15": 4.2,
    "calibration": {
        "csv_logging_enabled": True,
        "outcome_labeler": "offline_python_only",
        "shadow_compare": "v1_vs_v2",
        "bucket_report": "offline_python_only",
    },
    "market_structure": {
        "h1": "Bullish Continuation",
        "m15": "Bullish Continuation",
        "m5": "Bullish Pullback",
        "bullish_bos": True,
        "bearish_bos": False,
        "bullish_choch": False,
        "bearish_choch": False,
        "bullish_mss": False,
        "bearish_mss": False,
        "protected_high": 0.0,
        "protected_low": 3310.0,
    },
    "market_state": "TREND STRONG — WAIT FOR PULLBACK",
    "explanation": "Pullback Desk V2 experimental output.",
    "short_reason": "TREND STRONG — WAIT FOR PULLBACK",
    "reasons_positive": "Market extended;",
    "reasons_negative": "No HTF CHoCH confirmation;",
}


def test_pullback_v2_status_offline_empty():
    monitor_store.select_symbol("ZZPBV2OFF")
    client = TestClient(app)
    body = client.get("/api/v1/pullback/status").json()
    assert body["pullback_v2_supported"] is False
    assert body["pullback_v2"] is None


def test_pullback_v2_status_passthrough_from_heartbeat():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 3325.5,
            "ask": 3325.8,
            "digits": 2,
            "pullback_v2": SAMPLE_PULLBACK_V2,
        }
    )
    monitor_store.select_symbol("XAUUSD")
    client = TestClient(app)
    body = client.get("/api/v1/pullback/status").json()
    assert body["pullback_v2_supported"] is True
    assert body["pullback_v2"]["pullback_score"] == 68.0
    assert body["pullback_v2"]["displacement_score"] == 86.0
    assert body["pullback_v2"]["entry_location_score"] == 28.0
    assert body["pullback_v2"]["milestone"] == 7
    assert body["pullback_v2"]["version"] == "pullback_v2"
    assert body["pullback_v2"]["experimental"] is True
    assert body["pullback_v2"]["calibrated"] is False


def test_pullback_v1_and_v2_coexist():
    monitor_store.record_heartbeat(
        {
            "symbol": "EURUSD",
            "bid": 1.085,
            "ask": 1.0852,
            "digits": 5,
            "pullback": {
                "version": "1.0",
                "valid": True,
                "pullback_probability": 55.0,
                "continuation_probability": 25.0,
                "consolidation_probability": 12.0,
                "reversal_probability": 8.0,
            },
            "pullback_v2": SAMPLE_PULLBACK_V2,
        }
    )
    monitor_store.select_symbol("EURUSD")
    client = TestClient(app)
    body = client.get("/api/v1/pullback/status").json()
    assert body["pullback_supported"] is True
    assert body["pullback_v2_supported"] is True
    assert body["pullback"]["pullback_probability"] == 55.0
    assert body["pullback_v2"]["immediate_continuation_score"] == 51.0


def test_pullback_v2_m2_fields_passthrough():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 3350.0,
            "ask": 3350.3,
            "digits": 2,
            "pullback_v2": SAMPLE_PULLBACK_V2,
        }
    )
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/pullback/status").json()
    v2 = body["pullback_v2"]
    assert v2["dealing_range"]["location"] == "Deep Premium"
    assert v2["momentum"]["state"] == "EXTENDED"
    assert v2["displacement"]["bos"] == 100.0
    assert v2["liquidity"]["draw"] == "buy_side"
    assert v2["liquidity"]["state"] == "approaching"
    assert v2["poi"]["primary_type"] == "Fair Value Gap"
    assert v2["poi"]["pullback_target_score"] == 78.0
    assert v2["ote"]["poi_overlaps_ote"] is True
    assert v2["depth"]["source"] == "ote+poi"
    assert v2["depth"]["expected_depth"] == "MODERATE"
    assert v2["calibration"]["csv_logging_enabled"] is True
    assert v2["calibration"]["bucket_report"] == "offline_python_only"


def test_heartbeat_accepts_pullback_v2_field():
    token = get_settings().local_api_token
    client = TestClient(app)
    r = client.post(
        "/api/v1/heartbeat",
        json={
            "symbol": "XAUUSD",
            "bid": 2000.0,
            "ask": 2000.2,
            "digits": 2,
            "pullback_v2": SAMPLE_PULLBACK_V2,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    monitor_store.select_symbol("XAUUSD")
    st = client.get("/api/v1/pullback/status").json()
    assert st["pullback_v2_supported"] is True
    assert st["pullback_v2"]["reversal_risk_score"] == 12.0
