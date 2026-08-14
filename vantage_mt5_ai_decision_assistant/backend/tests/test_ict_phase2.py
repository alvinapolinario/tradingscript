"""ICT Phase 2 — heartbeat, PDH/PDL, rehydration tests."""
from __future__ import annotations

from app.analysis.ict.heartbeat import process_ict_heartbeat
from app.analysis.ict.liquidity import build_liquidity_levels
from app.analysis.ict.rehydrate import rehydrate_context_from_payload
from app.analysis.ict.session_levels import compute_previous_day_levels, previous_day_hl_from_d1
from app.analysis.ict.store import clear_store, get_persisted_setup, persist_setup_payload
from app.analysis.ict.types import DEFAULT_ICT_CONFIG, IctSetupContext, IctSetupState, LiquiditySweepEvent
from app.market_structure.types import Candle
from app.monitor_state import monitor_store
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _m15_series(n: int = 65, base: float = 4000.0, t0: int = 1_700_000_000) -> list[Candle]:
    return [_c(t0 + i * 900, base, base + 8, base - 2, base + 1) for i in range(n)]


def test_pdh_pdl_from_d1_previous_bar():
    d1 = [
        _c(1_700_000_000, 100, 110, 99, 105),
        _c(1_700_086_400, 105, 115, 104, 112),
    ]
    out = previous_day_hl_from_d1(d1)
    assert out is not None
    assert out[0] == 115.0
    assert out[1] == 104.0
    assert out[3] == "D1_PREVIOUS_BAR"


def test_pdh_pdl_prefers_d1_over_intraday():
    setup = _m15_series()
    d1 = [_c(1_699_900_000, 1, 2000, 0.5, 1999), _c(1_700_000_000, 1999, 2010, 1990, 2005)]
    pdh, pdl, _, source = compute_previous_day_levels(setup, d1, setup[-1].time, DEFAULT_ICT_CONFIG)
    assert source == "D1_PREVIOUS_BAR"
    assert pdh == 2010.0
    assert pdl == 1990.0


def test_liquidity_map_includes_pdh_pdl_meta():
    setup = _m15_series()
    d1 = [_c(1_700_000_000, 1, 4015, 3990, 4000)]
    bsl, ssl, meta = build_liquidity_levels(setup, 2.0, DEFAULT_ICT_CONFIG, d1_candles=d1, eval_time=setup[-1].time)
    kinds_bsl = {l.kind for l in bsl}
    kinds_ssl = {l.kind for l in ssl}
    assert "PDH" in kinds_bsl
    assert "PDL" in kinds_ssl
    assert meta.get("pdh_pdl_source") == "D1_PREVIOUS_BAR"


def test_rehydrate_restores_displacement_event():
    ctx = IctSetupContext(trade_bias="BEARISH", state=IctSetupState.LIQUIDITY_SWEPT, setup_id="ICT-TEST")
    payload = {
        "displacement_event": {
            "event_id": "DISP-ICT-TEST-1",
            "setup_id": "ICT-TEST",
            "direction": "BEARISH",
            "start_time": 100,
            "end_time": 200,
            "body_atr": 1.1,
            "quality": 75,
        },
        "entry_ready": True,
        "entry_event_id": "ENTRY-ICT-TEST-FVG1",
    }
    rehydrate_context_from_payload(ctx, payload)
    assert ctx.displacement_event is not None
    assert ctx.displacement_event.event_id == "DISP-ICT-TEST-1"
    assert ctx.entry_ready_emitted is True
    assert ctx.entry_event_id == "ENTRY-ICT-TEST-FVG1"


def test_persist_and_load_setup_payload():
    clear_store()
    payload = {"setup_id": "ICT-XAUUSD-M15-1-B", "symbol": "XAUUSD", "state": "WAITING_FOR_MSS"}
    persist_setup_payload(payload)
    loaded = get_persisted_setup("ICT-XAUUSD-M15-1-B")
    assert loaded is not None
    assert loaded["state"] == "WAITING_FOR_MSS"


def test_heartbeat_ict_candles_runs_python_engine():
    clear_store()
    m15 = _m15_series()
    m5 = [_c(c.time, c.open, c.high, c.low, c.close) for c in m15[-20:]]
    d1 = [_c(1_700_000_000, 3990, 4010, 3985, 4000)]
    legacy = {
        "module": "ict",
        "setup_state": "TRIGGERED",
        "decision": "BUY",
        "engine_source": "MQL5_LEGACY",
    }
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 4000.0,
            "spread_points": 20,
            "ict": legacy,
            "ict_candles": {
                "D1": [{"time": c.time, "open": c.open, "high": c.high, "low": c.low, "close": c.close} for c in d1],
                "M15": [{"time": c.time, "open": c.open, "high": c.high, "low": c.low, "close": c.close} for c in m15],
                "M5": [{"time": c.time, "open": c.open, "high": c.high, "low": c.low, "close": c.close} for c in m5],
            },
        }
    )
    monitor_store.select_symbol("XAUUSD")
    st = monitor_store.status()
    ict = (st.get("vantage_ea") or {}).get("ict") or {}
    assert ict.get("engine_source") == "PYTHON_CANONICAL"
    assert ict.get("source") == "heartbeat"
    assert ict.get("mql5_legacy", {}).get("decision") == "BUY"

    client = TestClient(app)
    body = client.get("/api/v1/ict/status").json()
    assert body.get("ict_python_engine") is True
    assert body["ict"]["engine_source"] == "PYTHON_CANONICAL"


def test_process_ict_heartbeat_returns_none_without_m15():
    assert process_ict_heartbeat({"symbol": "XAUUSD", "ict_candles": {"D1": []}}) is None
