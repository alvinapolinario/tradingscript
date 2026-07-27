"""Decision engine tests — dual new-entry / position risk classification."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.analysis.decision import classify_risk_status, decide
from app.analysis.technical import volume_step_ok, validate_symbol_sanity
from app.schemas import (
    AdvisoryAction,
    ExistingPositionDecision,
    NewEntryDecision,
    RiskStatus,
)
from conftest import as_request


def test_critical_risk_open_buy_profit_hold_with_caution():
    """Live-chart case: ~34.68% equity risk must be CRITICAL, not plain NO_TRADE/HOLD."""
    req = as_request(
        structure={
            "trend": "BEARISH",
            "note": "",
            "retest_pending": False,
            "support_break": False,
            "oversized_candle": False,
            "bear_reject": False,
            "nearest_support": "4088",
            "nearest_resistance": "4100",
        },
        indicators={"rsi14": 28.0},
        positions={
            "count": 1,
            "total_buy_volume": 0.02,
            "total_sell_volume": 0.0,
            "weighted_avg_entry": 4090.67,
            "total_floating_pl": 12.5,
            "items": [
                {
                    "ticket": 1,
                    "type": "BUY",
                    "volume": 0.02,
                    "price_open": 4090.67,
                    "price_current": 4095.0,
                    "sl": 4062.0,
                    "profit": 12.5,
                }
            ],
        },
        risk={
            "available": True,
            "status": "OK",
            "money_at_risk": 57.34,
            "equity_risk_pct": 34.68,
            "entry": 4090.67,
            "sl": 4062.0,
            "volume": 0.02,
        },
    )
    resp = decide(req)
    assert resp.risk_status == RiskStatus.CRITICAL
    assert resp.existing_position_decision == ExistingPositionDecision.HOLD_WITH_CAUTION
    assert resp.new_entry_decision in (
        NewEntryDecision.NO_NEW_TRADE,
        NewEntryDecision.RISK_BLOCKED,
    )
    assert resp.new_position_allowed is False
    assert resp.add_position_allowed is False
    assert resp.exceeds_max_position_risk is True
    assert resp.market_state == "BEARISH_EXHAUSTED"
    assert resp.estimated_money_risk == 57.34
    assert resp.equity_risk_pct == 34.68
    assert resp.entry == 4090.67
    assert resp.sl == 4062.0
    assert "Do not add exposure" in resp.risk_warning
    assert resp.action != AdvisoryAction.HOLD
    assert resp.action != AdvisoryAction.NO_TRADE
    assert resp.immediate_support == "4088\u20134090"
    assert resp.recovery_level_1 == "4100"
    assert resp.recovery_level_2 == "4105"
    assert resp.bullish_confirmation == "4112"


def test_critical_risk_losing_position_is_critical_risk():
    req = as_request(
        structure={"trend": "BEARISH", "note": "", "retest_pending": False, "oversized_candle": False},
        indicators={"rsi14": 40.0},
        positions={
            "count": 1,
            "total_buy_volume": 0.02,
            "weighted_avg_entry": 4090.67,
            "total_floating_pl": -20.0,
            "items": [{"ticket": 1, "type": "BUY", "volume": 0.02, "price_open": 4090.67, "price_current": 4080.0, "sl": 4062.0}],
        },
        risk={"available": True, "status": "OK", "money_at_risk": 57.34, "equity_risk_pct": 34.68, "entry": 4090.67, "sl": 4062.0},
    )
    resp = decide(req)
    assert resp.risk_status == RiskStatus.CRITICAL
    assert resp.existing_position_decision == ExistingPositionDecision.CRITICAL_RISK


def test_risk_bands():
    assert classify_risk_status(0.5, True) == RiskStatus.LOW
    assert classify_risk_status(1.5, True) == RiskStatus.MODERATE
    assert classify_risk_status(3.0, True) == RiskStatus.HIGH
    assert classify_risk_status(7.0, True) == RiskStatus.VERY_HIGH
    assert classify_risk_status(10.0, True) == RiskStatus.CRITICAL
    assert classify_risk_status(34.68, True) == RiskStatus.CRITICAL


def test_flat_impulse_wait():
    req = as_request()
    resp = decide(req)
    assert resp.new_entry_decision == NewEntryDecision.WAIT
    assert resp.existing_position_decision == ExistingPositionDecision.NONE


def test_high_spread_new_entry():
    req = as_request(
        prices={"high_spread": True, "spread_points": 900},
        environment="HIGH_SPREAD",
        structure={"note": "", "retest_pending": False, "support_break": False, "oversized_candle": False, "trend": "NEUTRAL"},
        positions={"count": 0, "items": []},
    )
    resp = decide(req)
    assert resp.new_entry_decision == NewEntryDecision.HIGH_SPREAD


def test_min_lot_0_01_volume_step():
    assert volume_step_ok(0.01, 0.01, 0.01, 100.0)
    assert not volume_step_ok(0.015, 0.01, 0.01, 100.0)


def test_three_digit_gold_pricing():
    req = as_request(symbol={"digits": 3, "point": 0.001})
    assert "unusual_digits" not in validate_symbol_sanity(req)
