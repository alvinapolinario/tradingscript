"""Smart Analyzer status + Take/Ignore decisions."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import signal_ledger as ledger
from app.main import app


def _ok_status(side_bias="BULLISH", symbol="XAUUSD"):
    strategy = {
        "h1_bias": side_bias,
        "m15_structure": side_bias,
        "h1_m15_aligned": True,
        "adx14": 24.0,
        "atr14": 12.5,
        "reward_risk_ratio": 2.0,
        "planned_equity_risk_pct": 0.50,
        "max_spread_points": 50,
        "news_available": True,
        "news_blocked": False,
        "minutes_to_high_impact": 120,
        "setup_age_m5": 1,
        "m5_closed_confirmed": True,
        "ema_stack_ok": True,
        "m5_trigger": side_bias,
        "allowed_direction": "BUY" if side_bias == "BULLISH" else "SELL",
    }
    return {
        "selected_symbol": symbol,
        "available_symbols": [symbol],
        "link_health": {
            "api_online": True,
            "ea_online": True,
            "any_ea_online": True,
            "overall": "CONNECTED",
        },
        "vantage_ea": {
            "connected": True,
            "seconds_since_seen": 2,
            "symbol": symbol,
            "company": "Vantage Markets (Pty) Ltd.",
            "spread_points": 20,
            "high_spread": False,
            "bid": 4100.0,
            "ask": 4100.3,
            "digits": 2,
            "market_state": "Transition",
            "strategy": strategy,
        },
    }


@pytest.fixture()
def tmp_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "signal_ledger.db"
    monkeypatch.setattr(ledger, "_DB_PATH", db)
    monkeypatch.setattr(ledger, "_DATA_DIR", tmp_path)
    ledger.init_db()
    return db


def test_analyzer_status_preview(tmp_ledger):
    st = ledger.build_analyzer_status(_ok_status(), mode="STANDARD")
    assert st["advisory_only"] is True
    assert st["decision_state"] == "AWAITING_YOUR_DECISION"
    assert st["active_signal"]["side"] == "BUY"
    assert st["active_signal"].get("preview") is True
    assert "Vantage" in st["broker"]
    assert st["votes"]["buy_points"] >= st["votes"]["sell_points"]


def test_record_take_decision(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    updated = ledger.record_decision(accepted["id"], "TAKE")
    assert updated["user_decision"] == "TAKE"
    assert updated["decided_utc"]
    # Same setup stays TAKEN — no lookalike preview that invites another Take
    st = ledger.build_analyzer_status(_ok_status())
    assert st["decision_state"] == "TAKEN"
    assert st["active_signal"]["id"] == accepted["id"]
    assert not st["active_signal"].get("preview")
    assert ledger.latest_pending_for_symbol("XAUUSD") is None


def test_take_does_not_duplicate_when_price_moves(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    ledger.record_decision(accepted["id"], "TAKE")
    st = _ok_status()
    st["vantage_ea"]["bid"] = 3305.0
    st["vantage_ea"]["ask"] = 3305.2
    assert ledger.maybe_accept_from_monitor(st) is None
    assert len(ledger.list_signals()) == 1


def test_reject_redecide(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    ledger.record_decision(accepted["id"], "IGNORE")
    with pytest.raises(ValueError, match="already decided"):
        ledger.record_decision(accepted["id"], "TAKE")


def test_prefers_ea_levels(tmp_ledger):
    st = _ok_status()
    st["vantage_ea"]["strategy"]["entry"] = 4100.0
    st["vantage_ea"]["strategy"]["stop"] = 4080.0
    st["vantage_ea"]["strategy"]["target"] = 4140.0
    accepted = ledger.maybe_accept_from_monitor(st)
    assert accepted is not None
    items = ledger.list_signals()
    assert items[0]["stop"] == 4080.0
    assert items[0]["target"] == 4140.0
    assert items[0]["timeframe"] == "M5"


def test_alignment_total_is_three(tmp_ledger):
    st = ledger.build_analyzer_status(_ok_status())
    assert st["alignment"]["total"] == 3
    assert st["alignment"]["aligned"] == 3


def test_no_signal_clears_votes(tmp_ledger):
    st = _ok_status()
    st["vantage_ea"]["strategy"]["h1_m15_aligned"] = False
    st["vantage_ea"]["strategy"]["m15_structure"] = "BEARISH"
    out = ledger.build_analyzer_status(st)
    assert out["decision_state"] == "NO_SIGNAL"
    assert out["active_signal"] is None
    assert out["votes"] == {
        "buy_votes": 0,
        "buy_points": 0,
        "sell_votes": 0,
        "sell_points": 0,
    }


def test_decision_api(tmp_ledger, monkeypatch):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    client = TestClient(app)
    r = client.post(f"/api/v1/signals/{accepted['id']}/decision", json={"decision": "IGNORE"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["signal"]["user_decision"] == "IGNORE"
    assert "no MT5 order" in body["caption"]


def test_invalid_decision_raises(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    with pytest.raises(ValueError):
        ledger.record_decision(accepted["id"], "BUY_NOW")
