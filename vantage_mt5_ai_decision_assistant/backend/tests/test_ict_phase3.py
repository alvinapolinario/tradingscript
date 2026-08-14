"""ICT Phase 3 — legacy suppression, advisory cards, entry triggers, replay API."""
from __future__ import annotations

from app.analysis.confluence import compute_confluence_from_ea
from app.analysis.ict.advisory_cards import build_ict_advisory_cards
from app.analysis.ict.entry_trigger import fvg_interaction_met
from app.analysis.ict.replay import replay_ict_sequence
from app.analysis.ict.types import EntryTriggerMode, IctConfig
from app.market_structure.types import Candle, FvgZone
from app.monitor_state import monitor_store
from fastapi.testclient import TestClient

from app.main import app


def _c(t, o, h, l, cl):
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _fvg():
    return FvgZone(
        fvg_id="FVG-B-M5-1",
        direction="BULLISH",
        timeframe="M5",
        created_time=100,
        lower=1.0,
        upper=1.1,
        gap_size=0.1,
        gap_atr=0.5,
        displacement_score=50,
    )


def test_entry_trigger_touch():
    f = _fvg()
    ok, kind = fvg_interaction_met(f, price=1.05, last_exec_candle=None, mode=EntryTriggerMode.TOUCH, atr_exec=0.01)
    assert ok and kind == "TOUCH"


def test_entry_trigger_ce():
    f = _fvg()
    ok, kind = fvg_interaction_met(f, price=1.05, last_exec_candle=None, mode=EntryTriggerMode.CE_TOUCH, atr_exec=0.01)
    assert ok and kind == "CE_TOUCH"


def test_entry_trigger_closed_bar():
    f = _fvg()
    bar = _c(1, 1.02, 1.08, 0.98, 1.06)
    ok, kind = fvg_interaction_met(
        f, price=1.2, last_exec_candle=bar, mode=EntryTriggerMode.CLOSED_BAR_TOUCH, atr_exec=0.01,
    )
    assert ok and kind == "CLOSED_BAR_TOUCH"


def test_advisory_cards_entry_ready_python_only():
    ea = {
        "symbol": "XAUUSD",
        "ict": {
            "valid": True,
            "engine_source": "PYTHON_CANONICAL",
            "entry_ready": True,
            "causality_valid": True,
            "decision": "SELL",
            "state": "ENTRY_READY",
            "setup_id": "ICT-XAUUSD-M15-1-S",
            "execution_fvg": {"lower": 4000, "upper": 4005},
            "stop_loss": {"price": 4015},
            "confidence_score": 78,
        },
    }
    cards = build_ict_advisory_cards(ea)
    assert len(cards) == 1
    assert cards[0]["source"] == "ICT"
    assert cards[0]["side"] == "SELL"


def test_advisory_cards_skip_mql5_legacy():
    ea = {
        "ict": {
            "valid": True,
            "engine_source": "MQL5_LEGACY",
            "entry_ready": True,
            "decision": "BUY",
        },
    }
    assert build_ict_advisory_cards(ea) == []


def test_confluence_ict_entry_ready_active():
    ea = {
        "ict_python_engine": True,
        "ict": {
            "valid": True,
            "engine_source": "PYTHON_CANONICAL",
            "entry_ready": True,
            "causality_valid": True,
            "decision": "BUY",
            "state": "ENTRY_READY",
            "confidence_score": 80,
            "timestamp": 1_700_000_000,
        },
    }
    conf = compute_confluence_from_ea(ea)
    ict = conf["components"]["ICT"]
    assert ict["direction"] == "LONG"
    assert ict["contribution"] > 0


def test_confluence_skips_mql5_when_python_active():
    ea = {
        "ict_python_engine": True,
        "ict": {
            "valid": True,
            "engine_source": "MQL5_LEGACY",
            "decision": "BUY",
            "confidence_score": 99,
        },
    }
    conf = compute_confluence_from_ea(ea)
    assert "ICT" not in conf["components"]


def test_ict_replay_api():
    candles = [_c(1_700_000_000 + i * 900, 4000, 4008, 3998, 4001) for i in range(65)]
    rows = [{"time": c.time, "open": c.open, "high": c.high, "low": c.low, "close": c.close} for c in candles]
    client = TestClient(app)
    r = client.post("/api/v1/ict/replay", json={"symbol": "XAUUSD", "candles": {"M15": rows, "M5": rows[-10:]}})
    assert r.status_code == 200
    data = r.json()
    assert data["step_count"] >= 1
    assert "steps" in data


def test_signals_api_merges_ict_advisory_cards():
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "ict": {
                "valid": True,
                "engine_source": "PYTHON_CANONICAL",
                "entry_ready": True,
                "causality_valid": True,
                "decision": "SELL",
                "state": "ENTRY_READY",
                "execution_fvg": {"lower": 4000, "upper": 4005},
                "confidence_score": 75,
            },
        }
    )
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/signals").json()
    ict_cards = [c for c in body["advisory_cards"] if c.get("source") == "ICT"]
    assert len(ict_cards) == 1
    assert ict_cards[0]["side"] == "SELL"


def test_discord_skips_mql5_legacy(monkeypatch):
    from app.ict_discord_notify import maybe_ict_alert, reset_state_for_tests

    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    sent = {"n": 0}

    def _send(**kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert(
        {
            "ict": {
                "valid": True,
                "engine_source": "MQL5_LEGACY",
                "setup_state": "TRIGGERED",
                "state_changed": True,
                "confidence_score": 90,
            }
        }
    )
    assert sent["n"] == 0
