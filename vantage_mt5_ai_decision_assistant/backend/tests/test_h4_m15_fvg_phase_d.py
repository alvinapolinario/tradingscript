"""Phase D tests — advisory cards, confluence, session scoring."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.analysis.confluence import normalize_ea_signals
from app.analysis.h4_m15_fvg.advisory_cards import build_h4_m15_advisory_cards
from app.analysis.h4_m15_fvg.engine import score_setup
from app.analysis.h4_m15_fvg.types import DEFAULT_H4_M15_CONFIG, H4M15Setup, H4M15SetupState
from app.analysis.master_verdict import build_master_verdict
from app.main import app
from app.market_structure.types import FvgZone
from app.monitor_state import monitor_store


def _entry_ready_primary(**overrides) -> dict:
    base = {
        "symbol": "EURUSD",
        "direction": "BULLISH",
        "state": "ENTRY_READY",
        "decision": "ENTRY_READY",
        "setup_id": "EURUSD-H4-1",
        "score": 78.5,
        "grade": "HIGH",
        "entry_price": 1.0850,
        "structural_stop": 1.0840,
        "entry_ready_time": 1_700_000_000,
        "entry_fvg": {"lower": 1.0848, "upper": 1.0852, "fvg_id": "M15-1"},
        "liquidity": {"sweep_detected": True},
        "structure": {"mss_confirmed": True},
        "reasons": ["Retrace into M15 FVG"],
    }
    base.update(overrides)
    return base


def test_build_h4_m15_advisory_cards_entry_ready():
    ea = {
        "symbol": "EURUSD",
        "h4_m15_fvg": {
            "valid": True,
            "decision": "ENTRY_READY",
            "primary": _entry_ready_primary(),
        },
    }
    cards = build_h4_m15_advisory_cards(ea)
    assert len(cards) == 1
    card = cards[0]
    assert card["source"] == "H4_M15_FVG"
    assert card["side"] == "BUY"
    assert card["entry_low"] == 1.0848
    assert card["desk_path"] == "/h4-m15-fvg"


def test_build_h4_m15_advisory_cards_skips_monitor():
    ea = {
        "h4_m15_fvg": {
            "valid": True,
            "decision": "MONITOR",
            "primary": _entry_ready_primary(state="WAITING_FOR_RETRACE", decision="NO ENTRY YET"),
        },
    }
    assert build_h4_m15_advisory_cards(ea) == []


def test_signals_api_includes_advisory_cards():
    monitor_store.select_symbol("EURUSD")
    monitor_store.record_heartbeat(
        {
            "symbol": "EURUSD",
            "connected": True,
            "h4_m15_fvg": {
                "valid": True,
                "decision": "ENTRY_READY",
                "primary": _entry_ready_primary(),
            },
        }
    )
    client = TestClient(app)
    body = client.get("/api/v1/signals?limit=10").json()
    assert body["advisory_card_count"] == 1
    assert body["advisory_cards"][0]["side"] == "BUY"


def test_normalize_ea_includes_h4_m15_fvg():
    ea = {
        "connected": True,
        "h4_m15_fvg": {
            "valid": True,
            "primary": _entry_ready_primary(direction="BEARISH", score=81.0),
        },
    }
    signals = normalize_ea_signals(ea)
    names = {s.strategy for s in signals}
    assert "H4_M15_FVG" in names
    fvg = next(s for s in signals if s.strategy == "H4_M15_FVG")
    assert fvg.direction == "SHORT"
    assert fvg.active is True
    assert fvg.confidence == 81.0


def test_master_verdict_h4_m15_chip():
    mv = build_master_verdict(
        {
            "connected": True,
            "h4_m15_fvg": {
                "valid": True,
                "decision": "ENTRY_READY",
                "primary": _entry_ready_primary(),
            },
        }
    )
    names = [m["name"] for m in mv["modules"]]
    assert "H4→M15" in names


def _minimal_entry_ready_setup() -> H4M15Setup:
    fvg = FvgZone(
        fvg_id="H4-1",
        direction="BULLISH",
        timeframe="H4",
        created_time=100,
        lower=100.0,
        upper=102.0,
        gap_size=2.0,
        gap_atr=0.5,
        displacement_score=60.0,
    )
    ef = FvgZone(
        fvg_id="M15-1",
        direction="BULLISH",
        timeframe="M15",
        created_time=200,
        lower=101.0,
        upper=101.5,
        gap_size=0.5,
        gap_atr=0.2,
        displacement_score=55.0,
        parent_fvg_id="H4-1",
    )
    from app.analysis.ict.types import LiquiditySweepEvent

    setup = H4M15Setup(
        setup_id="S1",
        symbol="EURUSD",
        direction="BULLISH",
        state=H4M15SetupState.ENTRY_READY,
        htf_fvg=fvg,
        entry_fvg=ef,
        pd_location="DISCOUNT",
        htf_bias="BULLISH",
        bias_alignment=True,
        displacement_score=70.0,
        displacement_time=150,
        mss_time=160,
        mss_price=101.2,
        entry_ready_time=170,
        entry_ready_emitted=True,
        sweep=LiquiditySweepEvent(
            detected=True,
            sweep_type="SELL_SIDE",
            trade_bias="BULLISH",
            level=100.8,
            sweep_price=100.5,
            sweep_time=120,
            penetration=0.3,
            closed_back_inside=True,
            quality_score=80.0,
        ),
    )
    return setup


def test_session_score_boosts_entry_ready_total():
    setup = _minimal_entry_ready_setup()
    cfg = DEFAULT_H4_M15_CONFIG
    london_ts = int(datetime(2024, 6, 3, 10, 0, tzinfo=timezone.utc).timestamp())
    off_ts = int(datetime(2024, 6, 3, 22, 0, tzinfo=timezone.utc).timestamp())
    london_score, _ = score_setup(setup, cfg, broker_time_unix=london_ts)
    off_score, _ = score_setup(setup, cfg, broker_time_unix=off_ts)
    assert london_score > off_score
    assert london_score - off_score >= 1.5
