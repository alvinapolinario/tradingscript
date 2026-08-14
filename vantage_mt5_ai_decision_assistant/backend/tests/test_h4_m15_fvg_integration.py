"""Integration tests — H4→M15 FVG heartbeat passthrough and full bullish flow."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.analysis.h4_m15_fvg.service import analyze_h4_m15_fvg
from app.analysis.h4_m15_fvg.store import clear_store
from app.analysis.h4_m15_fvg.types import H4M15SetupState
from app.main import app
from app.market_structure.types import Candle
from app.monitor_state import monitor_store


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def build_bullish_entry_ready_fixture() -> tuple[list[Candle], list[Candle]]:
    """Synthetic H4/M15 sequence: touch → sweep → displacement → MSS → FVG → ENTRY_READY."""
    step = 900
    h4_step = 14_400
    h4: list[Candle] = []
    t_h4 = 40_000
    for _ in range(35):
        h4.append(_c(t_h4, 1.0860, 1.0863, 1.0857, 1.0860))
        t_h4 += h4_step
    h4.extend(
        [
            _c(t_h4, 1.0838, 1.0845, 1.0837, 1.0840),
            _c(t_h4 + h4_step, 1.0846, 1.0860, 1.0846, 1.0855),
            _c(t_h4 + 2 * h4_step, 1.0855, 1.0865, 1.0850, 1.0860),
        ]
    )

    t0 = 200_000
    m15: list[Candle] = []
    for i in range(35):
        p = 1.0860
        m15.append(_c(t0 + i * step, p, p + 0.0002, p - 0.0002, p))

    base = t0 + 35 * step
    seq = [
        _c(base + 0 * step, 1.08510, 1.08520, 1.08505, 1.08515),
        _c(base + 1 * step, 1.08515, 1.08528, 1.08510, 1.08522),
        _c(base + 2 * step, 1.08520, 1.08532, 1.08512, 1.08525),
        _c(base + 3 * step, 1.08522, 1.08530, 1.08515, 1.08524),
        _c(base + 4 * step, 1.08520, 1.08528, 1.08445, 1.08512),
        _c(base + 5 * step, 1.08510, 1.08518, 1.08442, 1.08508),
        _c(base + 6 * step, 1.08505, 1.08512, 1.08438, 1.08455),
        _c(base + 7 * step, 1.08455, 1.08505, 1.08440, 1.08495),
        _c(base + 8 * step, 1.08495, 1.08505, 1.08442, 1.08500),
        _c(base + 9 * step, 1.08500, 1.08510, 1.08488, 1.08498),
        _c(base + 10 * step, 1.08490, 1.08495, 1.08418, 1.08452),
        _c(base + 11 * step, 1.08452, 1.08540, 1.08445, 1.08535),
        _c(base + 12 * step, 1.08480, 1.08485, 1.08478, 1.08482),
        _c(base + 13 * step, 1.08482, 1.08500, 1.08480, 1.08498),
        _c(base + 14 * step, 1.08498, 1.08520, 1.08505, 1.08515),
        _c(base + 15 * step, 1.08510, 1.08512, 1.08490, 1.08495),
    ]
    m15.extend(seq)
    return h4, m15


def _candles_to_payload(candles: list[Candle]) -> list[dict]:
    return [c.__dict__ for c in candles]


def test_bullish_flow_entry_ready_integration():
    clear_store()
    h4, m15 = build_bullish_entry_ready_fixture()
    out = analyze_h4_m15_fvg(
        symbol="EURUSD",
        candles_h4=h4,
        candles_m15=m15,
        persist=False,
    )
    assert out["valid"] is True
    setups = out["setups"]
    assert setups
    states = {s["state"] for s in setups}
    assert H4M15SetupState.ENTRY_READY.value in states or out.get("entry_ready_count", 0) > 0
    if out.get("entry_ready_count", 0) > 0:
        primary = out["primary"]
        assert primary["decision"] == "ENTRY_READY"
        assert primary["liquidity"]["sweep_detected"] is True
        assert primary["structure"]["mss_confirmed"] is True
        assert primary["entry_fvg"]["lower"] > 0
        assert primary.get("rejections") in (None, [])


def test_heartbeat_candles_populate_monitor_store():
    clear_store()
    h4, m15 = build_bullish_entry_ready_fixture()
    monitor_store.record_heartbeat(
        {
            "symbol": "EURUSD",
            "connected": True,
            "digits": 5,
            "bid": 1.0850,
            "h4_m15_fvg_candles": {
                "H4": _candles_to_payload(h4),
                "M15": _candles_to_payload(m15),
            },
        }
    )
    monitor_store.select_symbol("EURUSD")
    client = TestClient(app)
    body = client.get("/api/v1/h4-m15-fvg/status").json()
    assert body["h4_m15_fvg_supported"] is True
    assert body["h4_m15_fvg"] is not None
    assert body["h4_m15_fvg"]["valid"] is True
    assert body["module"] == "h4_m15_fvg"


def test_h4_m15_fvg_status_offline():
    monitor_store.select_symbol("ZZH4M15OFF")
    client = TestClient(app)
    body = client.get("/api/v1/h4-m15-fvg/status").json()
    assert body["advisory_only"] is True
    assert body["ea_online"] is False
