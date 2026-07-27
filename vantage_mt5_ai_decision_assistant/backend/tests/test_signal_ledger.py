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
