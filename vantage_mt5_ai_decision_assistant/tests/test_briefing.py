"""Decision briefing tests for monitor analysis panel."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.analysis.briefing import build_decision_brief


def test_critical_open_position_brief():
    brief = build_decision_brief(
        {
            "connected": True,
            "symbol": "XAUUSD",
            "trend": "BEARISH",
            "market_state": "BEARISH_EXHAUSTED",
            "new_entry_decision": "NO_NEW_TRADE",
            "existing_position_decision": "HOLD_WITH_CAUTION",
            "risk_status": "CRITICAL",
            "equity_risk_pct": 34.68,
            "estimated_sl_loss": 57.34,
            "entry": 4090.67,
            "sl": 4062.0,
            "floating_pl": 12.0,
            "position_count": 1,
            "nearest_support": "4088–4090",
            "recovery_level_1": "4100",
            "recovery_level_2": "4105",
            "bullish_confirmation": "4112",
            "technical_invalidation": "Close below SL 4062.00",
            "exceeds_max_position_risk": True,
            "add_position_allowed": False,
            "new_position_allowed": False,
            "risk_warning": "Position risk exceeds configured maximum. Do not add exposure or widen the stop.",
        }
    )
    assert brief["severity"] == "critical"
    assert "CRITICAL" in brief["headline"] or "caution" in brief["headline"].lower()
    assert any(r["priority"] == "critical" for r in brief["recommendations"])
    assert any("Do not add exposure" in r["detail"] for r in brief["recommendations"])
    assert brief["improvements"]
    assert any(not c["ok"] for c in brief["checklist"] if "risk" in c["label"].lower())


def test_float_profit_target_brief():
    brief = build_decision_brief(
        {
            "connected": True,
            "symbol": "XAUUSD",
            "trend": "BEARISH",
            "market_state": "BEARISH_EXHAUSTED",
            "new_entry_decision": "NO_NEW_TRADE",
            "existing_position_decision": "HOLD",
            "risk_status": "LOW",
            "equity_risk_pct": 0.8,
            "position_count": 1,
            "floating_pl": 25.0,
            "equity": 200.0,
            "floating_pl_pct_of_equity": 12.5,
            "float_profit_target_pct": 10.0,
            "float_profit_target_hit": True,
            "add_position_allowed": False,
            "new_position_allowed": False,
        }
    )
    assert brief["equity_pie"]["target_hit"] is True
    assert brief["equity_pie"]["floating_pl_pct"] == 12.5
    assert any("Take-profit" in r["title"] or "profit" in r["title"].lower() for r in brief["recommendations"])
    assert any(not c["ok"] for c in brief["checklist"] if "Float profit" in c["label"])


def test_waiting_for_ea_brief():
    brief = build_decision_brief({"connected": False, "position_count": 0})
    assert brief["severity"] == "warn"
    assert "heartbeat" in brief["headline"].lower() or "Waiting" in brief["headline"]
