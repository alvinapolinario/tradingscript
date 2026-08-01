"""Monitor store maps broker gold symbols to XAUUSD for the web pair selector."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.monitor_state import MonitorStore, _canonical_monitor_symbol


def test_canonical_gold_suffixes():
    assert _canonical_monitor_symbol("XAUUSD+") == "XAUUSD"
    assert _canonical_monitor_symbol("XAUUSD.a") == "XAUUSD"
    assert _canonical_monitor_symbol("GOLD.pro") == "XAUUSD"
    assert _canonical_monitor_symbol("BTCUSDm") == "BTCUSD"


def test_heartbeat_xauusd_plus_connects_xauusd_slot():
    store = MonitorStore()
    store.record_heartbeat(
        {
            "symbol": "XAUUSD+",
            "bid": 2650.0,
            "ask": 2650.5,
            "new_entry_decision": "WAIT",
            "existing_position_decision": "HOLD",
            "risk_status": "LOW",
        }
    )
    store.select_symbol("XAUUSD")
    st = store.status()
    ea = st["vantage_ea"]
    assert ea["connected"] is True
    assert ea["symbol"] == "XAUUSD"
    assert ea["broker_symbol"] == "XAUUSD+"
    assert st["link_health"]["ea_online"] is True
