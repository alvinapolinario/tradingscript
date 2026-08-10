"""Accepted Signal Ledger — SETUP_OK → ACCEPTED cards."""
from pathlib import Path

import pytest

from app import signal_ledger as ledger


def _ok_status(side_bias="BEARISH", symbol="XAUUSD"):
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
        "allowed_direction": "SELL" if side_bias == "BEARISH" else "BUY",
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
            "spread_points": 20,
            "high_spread": False,
            "bid": 3300.0,
            "ask": 3300.2,
            "digits": 2,
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


def test_accepts_setup_ok(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    assert accepted["side"] == "SELL"
    assert accepted["symbol"] == "XAUUSD"
    assert accepted["status"] == "ACCEPTED"
    assert 50 <= accepted["score"] <= 98
    items = ledger.list_signals()
    assert len(items) == 1
    assert items[0]["entry_low"] < items[0]["entry_high"]
    assert items[0]["stop"] > items[0]["entry_high"]  # SELL stop above


def test_dedupes_within_window(tmp_ledger):
    a1 = ledger.maybe_accept_from_monitor(_ok_status())
    a2 = ledger.maybe_accept_from_monitor(_ok_status())
    assert a1 is not None
    assert a2 is None
    assert len(ledger.list_signals()) == 1


def test_dedupes_when_mid_ticks(tmp_ledger):
    a1 = ledger.maybe_accept_from_monitor(_ok_status())
    assert a1 is not None
    st = _ok_status()
    st["vantage_ea"]["bid"] = 3310.0
    st["vantage_ea"]["ask"] = 3310.3
    assert ledger.maybe_accept_from_monitor(st) is None
    assert len(ledger.list_signals()) == 1


def test_no_second_pending_while_open(tmp_ledger):
    a1 = ledger.maybe_accept_from_monitor(_ok_status())
    assert a1 is not None
    # Even a different structural fingerprint must not stack another PENDING card
    st = _ok_status(side_bias="BULLISH")
    st["vantage_ea"]["strategy"]["m5_trigger"] = "BULLISH"
    st["vantage_ea"]["strategy"]["allowed_direction"] = "BUY"
    assert ledger.maybe_accept_from_monitor(st) is None
    assert len(ledger.list_signals()) == 1


def test_rejects_when_not_setup_ok(tmp_ledger):
    st = _ok_status()
    st["vantage_ea"]["strategy"]["h1_m15_aligned"] = False
    st["vantage_ea"]["strategy"]["m15_structure"] = "BULLISH"
    assert ledger.maybe_accept_from_monitor(st) is None
    assert ledger.list_signals() == []


def test_list_filter_symbol(tmp_ledger):
    ledger.maybe_accept_from_monitor(_ok_status(symbol="XAUUSD"))
    # Force different fingerprint via mid change + symbol
    st = _ok_status(symbol="BTCUSD", side_bias="BULLISH")
    st["vantage_ea"]["bid"] = 65000.0
    st["vantage_ea"]["ask"] = 65010.0
    # Bypass dedupe by clearing after first — different symbol/fp
    ledger.maybe_accept_from_monitor(st)
    xs = ledger.list_signals(symbol="XAUUSD")
    assert len(xs) == 1
    assert xs[0]["symbol"] == "XAUUSD"


def test_clear_signals_all(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    assert ledger.clear_signals("all") == 1
    assert ledger.list_signals() == []


def test_clear_signals_decided_only(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    ledger.record_decision(accepted["id"], "TAKE")
    st = _ok_status(symbol="EURUSD", side_bias="BULLISH")
    pending2 = ledger.maybe_accept_from_monitor(st)
    assert pending2 is not None
    deleted = ledger.clear_signals("decided")
    assert deleted == 1
    items = ledger.list_signals()
    assert len(items) == 1
    assert items[0]["symbol"] == "EURUSD"
    assert items[0]["user_decision"] == "PENDING"


def test_clear_signals_pending_only(tmp_ledger):
    accepted = ledger.maybe_accept_from_monitor(_ok_status())
    assert accepted is not None
    ledger.record_decision(accepted["id"], "IGNORE")
    assert ledger.clear_signals("pending") == 0
    assert len(ledger.list_signals()) == 1
    assert ledger.clear_signals("all") == 1


def test_clear_signals_invalid_scope(tmp_ledger):
    with pytest.raises(ValueError, match="scope must be"):
        ledger.clear_signals("bogus")
