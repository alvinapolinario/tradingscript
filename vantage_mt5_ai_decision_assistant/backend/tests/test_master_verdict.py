"""Master verdict synthesis tests."""
from __future__ import annotations

from app.analysis.master_verdict import build_master_verdict


def test_offline():
    mv = build_master_verdict({"connected": False})
    assert mv["verdict"] == "OFFLINE"


def test_critical_risk():
    mv = build_master_verdict(
        {
            "connected": True,
            "risk_status": "CRITICAL",
            "exceeds_max_position_risk": True,
            "equity_risk_pct": 12.0,
        }
    )
    assert mv["verdict"] == "CRITICAL"


def test_strong_swing():
    mv = build_master_verdict(
        {
            "connected": True,
            "symbol": "XAUUSD",
            "new_entry_decision": "WAIT",
            "risk_status": "LOW",
            "swing_strategy": {
                "valid": True,
                "signal": "STRONG SWING BUY",
                "confidence": 91.0,
                "entry_quality": "Excellent",
            },
        }
    )
    assert mv["verdict"] == "STRONG"
    assert mv["side"] == "BUY"


def test_watch_unconfirmed_liq():
    mv = build_master_verdict(
        {
            "connected": True,
            "new_entry_decision": "WAIT",
            "liquidity_grab": {
                "valid": True,
                "status": "LIQUIDITY_SWEEP_UNCONFIRMED",
                "confidence_score": 50,
            },
            "breakout_structure": {"valid": True, "grade_label": "Reject", "confidence_score": 43},
        }
    )
    assert mv["verdict"] in ("WATCH", "NO TRADE")
    assert any("unconfirmed" in b.lower() for b in mv["blocks"])
