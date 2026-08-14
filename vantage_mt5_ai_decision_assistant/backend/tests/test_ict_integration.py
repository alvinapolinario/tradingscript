"""Step 13 — ICT pipeline integration tests (MT5 payload → structure → ICT → confluence → API)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.analysis.ai_validation import build_strategy_validation_context
from app.analysis.confluence import compute_confluence_from_ea
from app.analysis.ict import analyze_ict_strategy
from app.analysis.ict.state_store import clear_store, get_active_setup
from app.analysis.ict.types import IctConfig
from app.analysis.master_verdict import build_master_verdict
from app.main import app
from app.market_structure import (
    atr,
    candles_from_payload,
    detect_fvgs,
    find_swings,
    validate_candles,
)
from app.market_structure.types import Candle
from app.monitor_state import monitor_store


def _bearish_ict_series() -> tuple[list[Candle], list[Candle]]:
    """Craft M15 setup + M5 execution series with BSL sweep → bearish ICT path."""
    setup: list[Candle] = []
    base = 4000.0
    t = 1_700_000_000
    for i in range(40):
        setup.append(_c(t + i * 900, base, base + 8, base - 2, base + 1))
    setup.append(_c(t + 40 * 900, base + 5, base + 12, base + 4, base + 6))
    setup.append(_c(t + 41 * 900, base + 6, base + 10, base + 5, base + 7))
    setup.append(_c(t + 42 * 900, base + 7, base + 11, base + 6, base + 8))
    bsl_level = base + 11.0
    setup.append(_c(t + 43 * 900, base + 8, bsl_level + 1.5, base + 7, base + 9.5))
    setup.append(_c(t + 44 * 900, base + 9, base + 10, base + 2, base + 3))
    setup.append(_c(t + 45 * 900, base + 3, base + 4, base - 1, base + 0.5))
    setup.append(_c(t + 46 * 900, base + 0.5, base + 1, base - 3, base - 2.5))
    et = t + 43 * 900
    exec_candles = [
        _c(et, base + 9, bsl_level + 1.2, base + 8, base + 9.8),
        _c(et + 300, base + 9.5, base + 10, base + 5, base + 5.5),
        _c(et + 600, base + 5, base + 6, base + 4, base + 4.5),
        _c(et + 900, base + 4.5, base + 5, base + 1, base + 1.5),
        _c(et + 1200, base + 1.5, base + 2.5, base + 0.5, base + 2.0),
        _c(et + 1500, base + 2.0, base + 3.5, base + 1.8, base + 3.0),
    ]
    return setup, exec_candles


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _to_mt5_rows(candles: list[Candle]) -> list[dict]:
    return [
        {"time": c.time, "open": c.open, "high": c.high, "low": c.low, "close": c.close, "volume": c.volume}
        for c in candles
    ]


def _ict_cfg() -> IctConfig:
    return IctConfig(
        min_candles=40,
        displacement_min_score=35.0,
        displacement_min_body_atr=0.4,
        displacement_min_range_atr=0.4,
        displacement_min_body_ratio=0.45,
        min_confidence=50.0,
        minimum_rr=1.0,
        fvg_min_gap_atr=0.01,
    )


def _mt5_multi_tf_payload(setup: list[Candle], execution: list[Candle]) -> dict:
    """MT5-style multi-TF candle blob for POST /api/v1/ict/analyze."""
    h1 = setup[::4][:30] or setup[:30]
    cfg = _ict_cfg()
    retrace_bid = execution[-1].close if execution else setup[-1].close
    return {
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "market": {"bid": retrace_bid, "spread_points": 25},
        "config": {
            "min_confidence": cfg.min_confidence,
            "minimum_rr": cfg.minimum_rr,
            "displacement_min_score": cfg.displacement_min_score,
            "min_candles": cfg.min_candles,
            "fvg_min_gap_atr": cfg.fvg_min_gap_atr,
        },
        "candles": {
            "H1": _to_mt5_rows(h1),
            "M15": _to_mt5_rows(setup),
            "M5": _to_mt5_rows(execution),
        },
    }


def _run_ict(setup: list[Candle], execution: list[Candle]) -> dict:
    return analyze_ict_strategy(
        symbol="XAUUSD",
        candles_setup=setup,
        candles_execution=execution,
        bid=execution[-1].close if execution else setup[-1].close,
        cfg=_ict_cfg(),
    )


@pytest.fixture(autouse=True)
def _clean_ict_store():
    clear_store()
    yield
    clear_store()


def test_mt5_payload_through_market_structure_primitives():
    setup, exec_c = _bearish_ict_series()
    m15 = candles_from_payload(_to_mt5_rows(setup))
    assert validate_candles(m15) is None
    swings = find_swings(m15, left=2, right=2, atr_val=atr(m15))
    assert len(swings) >= 1
    fvgs = detect_fvgs(exec_c, timeframe="M5", atr=atr(exec_c), cfg=type("C", (), {"fvg_min_gap_atr": 0.01})())
    assert isinstance(fvgs, list)
    ict = _run_ict(m15, exec_c)
    assert ict["valid"] is True
    assert ict["liquidity"]["sweep_detected"] is True


def test_api_ict_analyze_full_pipeline():
    setup, exec_c = _bearish_ict_series()
    client = TestClient(app)
    r = client.post("/api/v1/ict/analyze", json=_mt5_multi_tf_payload(setup, exec_c))
    assert r.status_code == 200
    data = r.json()
    assert data["strategy"] == "ICT"
    assert data["valid"] is True
    assert "timeline" in data
    assert "score_gates" in data
    assert data["setup_id"].startswith("ICT-XAUUSD-M15")
    active = get_active_setup("XAUUSD", "M15")
    assert active is not None
    hist = client.get("/api/v1/strategies/ict/XAUUSD/history").json()
    assert hist["count"] >= 1


def test_ict_analyze_to_confluence_to_master_verdict():
    setup, exec_c = _bearish_ict_series()
    ict = _run_ict(setup, exec_c)
    ea = {
        "connected": True,
        "symbol": "XAUUSD",
        "new_entry_decision": "WAIT",
        "risk_status": "LOW",
        "ict": ict,
        "amd_ifvg": {
            "valid": True,
            "analysis_active": True,
            "decision": ict.get("decision") if ict.get("decision") in ("BUY", "SELL") else "WAIT",
            "confidence": 70,
            "setup_state": "MSS_CONFIRMED",
        },
    }
    conf = compute_confluence_from_ea(ea)
    assert conf["success"] is True
    assert conf["signals_count"] >= 1
    mv = build_master_verdict(ea)
    assert any(m["name"] == "ICT" for m in mv["modules"])
    assert mv["verdict"] in ("STRONG", "SETUP", "WATCH", "NO TRADE", "CRITICAL", "OFFLINE")


def test_confluence_api_endpoints():
    setup, exec_c = _bearish_ict_series()
    client = TestClient(app)
    ict = client.post("/api/v1/ict/analyze", json=_mt5_multi_tf_payload(setup, exec_c)).json()
    ea = {"connected": True, "symbol": "XAUUSD", "ict": ict}
    conf = client.post("/api/v1/confluence/analyze", json={"ea": ea}).json()
    assert conf["success"] is True
    assert "overall_direction" in conf
    assert "components" in conf


def test_heartbeat_ict_status_and_ai_validation_context():
    setup, exec_c = _bearish_ict_series()
    ict = _run_ict(setup, exec_c)
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "connected": True,
            "bid": setup[-1].close,
            "ict": ict,
        }
    )
    monitor_store.select_symbol("XAUUSD")
    client = TestClient(app)
    st = client.get("/api/v1/ict/status").json()
    assert st["ict_supported"] is True
    assert st["ict"]["setup_id"] == ict["setup_id"]
    ctx = build_strategy_validation_context(monitor_store.status())
    assert "ICT" in ctx["strategies"]
    assert ctx["strategies"]["ICT"]["backend_signal"] == ict["decision"]


def test_ict_page_and_status_links():
    setup, exec_c = _bearish_ict_series()
    client = TestClient(app)
    ict = client.post("/api/v1/ict/analyze", json=_mt5_multi_tf_payload(setup, exec_c)).json()
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "connected": True, "ict": ict})
    monitor_store.select_symbol("XAUUSD")
    page = client.get("/ict")
    assert page.status_code == 200
    assert "ICT Strategy" in page.text
    status = client.get("/api/v1/ict/status").json()
    assert status["links"]["ict"] == "/ict"


def test_ict_discord_on_analyze_state_change(monkeypatch):
    """Integration: analyze output shape feeds discord notifier on allowed state change."""
    sent: list[str] = []

    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)

    def _capture(signal_id, **kwargs):
        sent.append(signal_id)
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _capture)
    from app.ict_discord_notify import maybe_ict_alert, reset_state_for_tests

    reset_state_for_tests()
    setup, exec_c = _bearish_ict_series()
    ict = _run_ict(setup, exec_c)
    # Discord fires only on whitelisted states — merge engine result with alertable state
    alert_blob = {
        **ict,
        "state": "MSS_CONFIRMED",
        "setup_state": "MSS_CONFIRMED",
        "status": "MSS_CONFIRMED",
        "confidence_score": max(float(ict.get("confidence_score") or 0), 82),
        "state_changed": True,
    }
    maybe_ict_alert({"ict": alert_blob})
    assert len(sent) == 1
    assert ict["setup_id"] in sent[0]
    assert "MSS_CONFIRMED" in sent[0]


def test_confluence_status_from_monitor_store():
    setup, exec_c = _bearish_ict_series()
    ict = _run_ict(setup, exec_c)
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "connected": True,
            "ict": ict,
            "amd_ifvg": {
                "valid": True,
                "analysis_active": True,
                "decision": "SELL" if ict.get("decision") == "SELL" else "WAIT",
                "confidence": 72,
            },
        }
    )
    monitor_store.select_symbol("XAUUSD")
    body = TestClient(app).get("/api/v1/confluence/status").json()
    assert body["advisory_only"] is True
    assert "confluence" in body
    assert "master_verdict" in body
    assert any(m["name"] == "ICT" for m in body["master_verdict"]["modules"])


def test_ai_brief_structured_json_contains_ict_scores():
    setup, exec_c = _bearish_ict_series()
    ict = _run_ict(setup, exec_c)
    monitor_store.record_heartbeat({"symbol": "XAUUSD", "connected": True, "ict": ict})
    monitor_store.select_symbol("XAUUSD")
    brief = TestClient(app).get("/api/v1/monitor/ai-brief").json()
    ctx = brief["structured_context"]
    assert ctx["strategies"]["ICT"]["confidence"] == ict["confidence_score"]
    assert ict["setup_id"] in brief["markdown"] or ict["setup_state"] in brief["markdown"]
    # Round-trip: structured section is valid JSON
    section = brief["markdown"].split("```json\n", 1)[1].split("\n```", 1)[0]
    parsed = json.loads(section)
    assert parsed["backend_authoritative"] is True


def test_state_persists_across_repeated_analyze():
    setup, exec_c = _bearish_ict_series()
    payload = _mt5_multi_tf_payload(setup, exec_c)
    client = TestClient(app)
    r1 = client.post("/api/v1/ict/analyze", json=payload).json()
    r2 = client.post("/api/v1/ict/analyze", json=payload).json()
    assert r1["setup_id"] == r2["setup_id"]
    active = get_active_setup("XAUUSD", "M15")
    assert active is not None
    assert active.setup_id == r1["setup_id"]
