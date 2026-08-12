"""Pullback V2 Milestone 7 — calibration bucket report tests."""
from fastapi.testclient import TestClient

from app.main import app
from app.analysis.pullback_v2.calibration_buckets import (
    build_calibration_report,
    build_score_buckets,
    lookup_calibrated_probability,
)


def _labeled_row(score: float, occurred: bool, *, v1: float | None = None) -> dict:
    return {
        "v2_pullback_score": score,
        "v1_pullback_prob": v1 if v1 is not None else score,
        "outcome": {
            "label_status": "ok",
            "pullback_occurred": occurred,
            "reversal_before_pullback": False,
        },
    }


def test_build_score_buckets_monotonic():
    rows = (
        [_labeled_row(5, False)] * 5
        + [_labeled_row(25, False)] * 5
        + [_labeled_row(55, True)] * 5
        + [_labeled_row(75, True)] * 5
    )
    report = build_score_buckets(rows, "v2_pullback_score")
    assert report["labeled_count"] == 20
    buckets = {b["label"]: b for b in report["buckets"]}
    assert buckets["0-10"]["rate"] == 0.0
    assert buckets["20-30"]["rate"] == 0.0
    assert buckets["50-60"]["rate"] == 1.0
    assert buckets["70-80"]["rate"] == 1.0
    assert report["recommended_threshold"] is not None


def test_lookup_calibrated_probability():
    rows = [_labeled_row(72, True)] * 4 + [_labeled_row(78, True)] * 4
    part = build_score_buckets(rows, "v2_pullback_score", min_samples=2)
    rate = lookup_calibrated_probability(75, part["buckets"])
    assert rate == 1.0


def test_build_calibration_report_insufficient():
    report = build_calibration_report([_labeled_row(60, True)], min_samples=5)
    assert report["calibrated"] is False
    assert report["labeled_count"] == 1


def test_build_calibration_report_sufficient():
    rows = [_labeled_row(20 + i * 4, i % 2 == 0) for i in range(30)]
    report = build_calibration_report(rows, min_samples=3)
    assert report["milestone"] == 7
    assert "v2_pullback_score" in report["scores"]
    assert report["pullback_base_rate"] is not None


def test_calibrate_api():
    client = TestClient(app)
    rows = []
    candles = [{"open": 100, "high": 101, "low": 99, "close": 100}]
    for i in range(3):
        rows.append(
            {
                "dom_dir": 1,
                "ref_close": 100,
                "atr_m15": 2,
                "threshold_atr": 0.5,
                "protected_low": 95,
                "horizon_bars": 1,
                "v2_pullback_score": 40 + i * 15,
                "v1_pullback_prob": 40 + i * 15,
            }
        )
        candles.append({"open": 100, "high": 100.5, "low": 98.0, "close": 98.5})

    r = client.post(
        "/api/v1/pullback/v2/calibrate",
        json={"rows": rows, "candles_m15": candles, "min_samples": 1},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["calibration"]["module"] == "pullback_v2_calibration"
    assert data["labeler"]["row_count"] == 3


def test_shadow_analyze_with_calibration():
    client = TestClient(app)
    rows = []
    candles = [{"open": 100, "high": 101, "low": 99, "close": 100}]
    for i in range(4):
        rows.append(
            {
                "dom_dir": 1,
                "ref_close": 100,
                "atr_m15": 2,
                "threshold_atr": 0.5,
                "protected_low": 95,
                "horizon_bars": 1,
                "v2_pullback_score": 50 + i * 10,
                "v1_pullback_prob": 50 + i * 10,
            }
        )
        candles.append({"open": 100, "high": 100.5, "low": 98.0, "close": 98.5})

    r = client.post(
        "/api/v1/pullback/v2/shadow/analyze",
        json={
            "rows": rows,
            "candles_m15": candles,
            "include_calibration": True,
            "min_samples": 1,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "calibration" in data
    assert data["calibration"]["milestone"] == 7
