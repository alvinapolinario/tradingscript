"""Pullback V2 Milestone 6 — labeler + shadow comparison tests."""
from fastapi.testclient import TestClient

from app.main import app
from app.analysis.pullback_v2.outcome_labeler import label_pullback_outcome
from app.analysis.pullback_v2.shadow_compare import aggregate_shadow_metrics, live_shadow_compare


def test_label_pullback_outcome_bullish():
    row = {
        "dom_dir": 1,
        "ref_close": 100.0,
        "atr_m15": 2.0,
        "threshold_atr": 0.5,
        "protected_low": 95.0,
    }
    future = [
        {"high": 101, "low": 98.5, "close": 99.5},
        {"high": 100.5, "low": 98.0, "close": 98.5},
    ]
    out = label_pullback_outcome(row, future)
    assert out["label_status"] == "ok"
    assert out["pullback_occurred"] is True
    assert out["bars_to_pullback"] == 1


def test_label_pullback_reversal_first():
    row = {
        "dom_dir": 1,
        "ref_close": 100.0,
        "atr_m15": 2.0,
        "threshold_atr": 0.5,
        "protected_low": 99.0,
    }
    future = [{"high": 100, "low": 98.5, "close": 98.8}]
    out = label_pullback_outcome(row, future)
    assert out["reversal_before_pullback"] is True
    assert out["pullback_occurred"] is False


def test_live_shadow_compare_aligned():
    v1 = {
        "pullback_probability": 62,
        "continuation_probability": 18,
        "consolidation_probability": 12,
        "reversal_probability": 8,
    }
    v2 = {
        "pullback_score": 68,
        "immediate_continuation_score": 51,
        "continuation_after_pullback_score": 72,
        "reversal_risk_score": 12,
        "calibration": {"csv_logging_enabled": True},
    }
    shadow = live_shadow_compare(v1, v2)
    assert shadow["available"] is True
    assert shadow["v1_dominant_outcome"] == "pullback"
    assert shadow["aligned"] is True


def test_aggregate_shadow_metrics():
    rows = [
        {
            "v1_pullback_prob": 60,
            "v2_pullback_score": 70,
            "outcome": {"label_status": "ok", "pullback_occurred": True},
        },
        {
            "v1_pullback_prob": 40,
            "v2_pullback_score": 30,
            "outcome": {"label_status": "ok", "pullback_occurred": False},
        },
    ]
    m = aggregate_shadow_metrics(rows)
    assert m["labeled_count"] == 2
    assert m["v1_pullback_precision"] == 1.0
    assert m["v2_pullback_precision"] == 1.0


def test_shadow_analyze_api():
    client = TestClient(app)
    body = {
        "rows": [
            {
                "dom_dir": 1,
                "ref_close": 100,
                "atr_m15": 2,
                "threshold_atr": 0.5,
                "protected_low": 95,
                "horizon_bars": 2,
                "v1_pullback_prob": 65,
                "v2_pullback_score": 70,
            }
        ],
        "candles_m15": [
            {"open": 100, "high": 101, "low": 99, "close": 100},
            {"open": 100, "high": 100.5, "low": 98.5, "close": 99},
            {"open": 99, "high": 99.5, "low": 98, "close": 98.5},
        ],
    }
    r = client.post("/api/v1/pullback/v2/shadow/analyze", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["labeler"]["pullback_occurred_count"] == 1
    assert data["shadow"]["v2_pullback_precision"] == 1.0
