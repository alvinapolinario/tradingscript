"""Breakout Structure Intelligence — status API tests."""
from fastapi.testclient import TestClient

from app.analysis.breakout_structure_logic import BreakoutScoreInput, grade_from_score, score_breakout
from app.main import app
from app.monitor_state import monitor_store

SAMPLE_BOS = {
    "module": "breakout_structure",
    "version": "1.1",
    "valid": True,
    "gold_symbol_valid": True,
    "engine_enabled": True,
    "analysis_active": True,
    "symbol": "XAUUSD",
    "base_symbol": "XAUUSD",
    "status_line": "A | Score 86.0",
    "market_structure": "H4 Bearish (LH/LL) | H1 Bearish (LH/LL) | M15 Neutral",
    "market_structure_h4": "Bearish (LH/LL)",
    "market_structure_h1": "Bearish (LH/LL)",
    "market_structure_m15": "Neutral",
    "current_structure": "Bearish (LH-LL)",
    "structure_strength": "Strong",
    "bos_class": "Bearish BOS",
    "latest_bos_event": "Bearish BOS below 4035.00",
    "latest_choch_event": "",
    "trendline_type": "Bearish (LH)",
    "trendline_strength": 72.0,
    "trendline_touches": 4,
    "breakout_type": "Horizontal",
    "breakout_lifecycle": "Confirmed Close",
    "breakout_status": "Confirmed Close",
    "breakout_confidence": 82.0,
    "retest_lifecycle": "Approaching",
    "retest_status": "Retest Pending",
    "rbs_flip_lifecycle": "Waiting Retest",
    "sbr_flip_lifecycle": "Waiting",
    "sbr_status": "Waiting",
    "rbs_status": "Waiting Retest",
    "validation_progress": 75.0,
    "current_event": "Horizontal Breakout Detected",
    "expected_next_event": "Waiting for Retest",
    "ai_reasoning": "Bearish structure intact. Horizontal breakout confirmed close.",
    "breakout_valid": True,
    "confidence_score": 86.0,
    "signal_grade": "A",
    "institutional_probability": 78.5,
    "ml_prob_success": 82.0,
    "ml_prob_failure": 18.0,
    "ml_confidence": 82.0,
    "score_breakdown": "Structure 20; TL 11; Break 13; Retest 15;",
    "score_structure_pts": 20,
    "score_breakout_pts": 13,
    "score_trendline_pts": 11,
    "score_retest_pts": 8,
    "score_flip_pts": 10,
    "score_momentum_pts": 8,
    "recommendation": "Structural breakout conditions developing — monitor retest",
    "htf_aligned": True,
    "eval_bar_m5": 1710000000,
}


def test_breakout_status_offline_empty():
    monitor_store.select_symbol("ZZBOSOFF")
    body = TestClient(app).get("/api/v1/breakout-structure/status").json()
    assert body["breakout_structure_supported"] is False
    assert body["breakout_structure"] is None


def test_breakout_status_passthrough():
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "bid": 4040.0, "ask": 4040.2, "digits": 2, "breakout_structure": SAMPLE_BOS})
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/breakout-structure/status").json()
    assert body["breakout_structure_supported"] is True
    assert body["breakout_structure"]["signal_grade"] == "A"
    assert body["breakout_structure"]["confidence_score"] == 86.0


def test_breakout_page_served():
    r = TestClient(app).get("/breakout-structure")
    assert r.status_code == 200
    assert "BREAKOUT STRUCTURE" in r.text.upper()


def test_scoring_grade_thresholds():
    assert grade_from_score(96) == "Institutional Grade"
    assert grade_from_score(74) == "Reject"
    score, grade = score_breakout(BreakoutScoreInput(structure_pts=20, trendline_pts=15, breakout_pts=15, retest_pts=15, flip_pts=10, htf_pts=5))
    assert score >= 75
    assert grade in ("A", "A+", "Institutional Grade", "B+")
