"""H4 → M15 FVG engine tests."""
from __future__ import annotations

import copy

from app.analysis.h4_m15_fvg.engine import (
    H4M15Engine,
    _clear_stale_exec_fvg_rejection,
    _EXEC_FVG_DIRECTION_MISMATCH,
    displacement_ok,
    htf_touch_detected,
    select_execution_fvg,
)
from app.analysis.h4_m15_fvg.service import analyze_h4_m15_fvg
from app.analysis.h4_m15_fvg.store import clear_store
from app.analysis.h4_m15_fvg.types import DEFAULT_H4_M15_CONFIG, H4M15Setup, H4M15SetupState
from app.market_structure.fvg import apply_candle_mitigation, detect_fvgs
from app.market_structure.types import Candle, FvgStatus, FvgZone


class _GapCfg:
    fvg_min_gap_atr = 0.05
    ifvg_min_break_atr = 0.05
    ifvg_require_body_close = True


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _bullish_fvg_at(t: int, low: float = 100.0, gap: float = 2.0) -> list[Candle]:
    return [
        _c(t - 2, low, low + 1, low - 0.5, low + 0.5),
        _c(t - 1, low + 0.5, low + 3, low + 0.4, low + 2.5),
        _c(t, low + 2.5, low + gap + 3, low + 2.0, low + gap + 2),
    ]


def test_bullish_h4_fvg_detection():
    candles = _bullish_fvg_at(100)
    fvgs = detect_fvgs(candles, timeframe="H4", atr=2.0, cfg=_GapCfg(), symbol="EURUSD")
    assert len(fvgs) == 1
    assert fvgs[0].direction == "BULLISH"
    assert fvgs[0].lower == candles[0].high
    assert fvgs[0].upper == candles[2].low


def test_h4_mitigation_and_midpoint():
    candles = _bullish_fvg_at(100)
    fvg = detect_fvgs(candles, timeframe="H4", atr=2.0, cfg=_GapCfg())[0]
    mid = (fvg.lower + fvg.upper) / 2
    apply_candle_mitigation(fvg, _c(101, mid + 0.5, mid + 1, mid - 0.1, mid))
    assert fvg.first_touch_time == 101
    assert fvg.mitigation_pct > 0
    assert fvg.status in (FvgStatus.TOUCHED, FvgStatus.PARTIALLY_MITIGATED, FvgStatus.MIDPOINT_REACHED)


def test_displacement_thresholds():
    ok, score = displacement_ok(_c(1, 100, 104, 99, 103.5), atr=2.0, cfg=DEFAULT_H4_M15_CONFIG)
    assert ok is True
    assert score > 50
    weak, _ = displacement_ok(_c(2, 100, 100.5, 99.9, 100.1), atr=2.0, cfg=DEFAULT_H4_M15_CONFIG)
    assert weak is False


def test_execution_fvg_rejects_pre_touch():
    htf = FvgZone(
        fvg_id="H4-1",
        direction="BULLISH",
        timeframe="H4",
        created_time=100,
        lower=100,
        upper=102,
        gap_size=2,
        gap_atr=0.5,
        displacement_score=50,
    )
    setup = H4M15Setup(
        setup_id="S1",
        symbol="EURUSD",
        direction="BULLISH",
        state=H4M15SetupState.WAITING_FOR_LTF_FVG,
        htf_fvg=htf,
        htf_first_touch_time=200,
        mss_time=250,
        displacement_time=240,
    )
    early = FvgZone(
        fvg_id="M15-EARLY",
        direction="BULLISH",
        timeframe="M15",
        created_time=150,
        lower=100.5,
        upper=101.5,
        gap_size=1,
        gap_atr=0.2,
        displacement_score=40,
    )
    assert select_execution_fvg([early], setup, DEFAULT_H4_M15_CONFIG) is None


def test_execution_fvg_accepts_post_mss():
    htf = FvgZone(
        fvg_id="H4-1",
        direction="BULLISH",
        timeframe="H4",
        created_time=100,
        lower=100,
        upper=102,
        gap_size=2,
        gap_atr=0.5,
        displacement_score=50,
    )
    setup = H4M15Setup(
        setup_id="S1",
        symbol="EURUSD",
        direction="BULLISH",
        state=H4M15SetupState.WAITING_FOR_LTF_FVG,
        htf_fvg=htf,
        htf_first_touch_time=200,
        mss_time=250,
        displacement_time=240,
    )
    valid = FvgZone(
        fvg_id="M15-OK",
        direction="BULLISH",
        timeframe="M15",
        created_time=260,
        lower=100.8,
        upper=101.8,
        gap_size=1,
        gap_atr=0.2,
        displacement_score=60,
    )
    picked = select_execution_fvg([valid], setup, DEFAULT_H4_M15_CONFIG)
    assert picked is not None
    assert picked.fvg_id == "M15-OK"


def test_wrong_direction_fvg_rejected():
    htf = FvgZone(
        fvg_id="H4-1",
        direction="BULLISH",
        timeframe="H4",
        created_time=100,
        lower=100,
        upper=102,
        gap_size=2,
        gap_atr=0.5,
        displacement_score=50,
    )
    setup = H4M15Setup(
        setup_id="S1",
        symbol="EURUSD",
        direction="BULLISH",
        state=H4M15SetupState.WAITING_FOR_LTF_FVG,
        htf_fvg=htf,
        htf_first_touch_time=200,
        mss_time=250,
        displacement_time=240,
    )
    bear = FvgZone(
        fvg_id="M15-BEAR",
        direction="BEARISH",
        timeframe="M15",
        created_time=260,
        lower=98,
        upper=99,
        gap_size=1,
        gap_atr=0.2,
        displacement_score=60,
    )
    assert select_execution_fvg([bear], setup, DEFAULT_H4_M15_CONFIG) is None


def test_htf_touch_detected_bullish():
    htf = FvgZone(
        fvg_id="H4-1",
        direction="BULLISH",
        timeframe="H4",
        created_time=1,
        lower=100,
        upper=102,
        gap_size=2,
        gap_atr=0.5,
        displacement_score=50,
    )
    setup = H4M15Setup(
        setup_id="S1",
        symbol="EURUSD",
        direction="BULLISH",
        state=H4M15SetupState.WAITING_FOR_HTF_MITIGATION,
        htf_fvg=htf,
    )
    assert htf_touch_detected(setup, _c(2, 103, 103.5, 101.5, 102)) is True


def test_replay_no_lookahead_on_touch():
    """Incremental processing matches fresh replay at each bar (no future leakage)."""
    h4 = []
    for i in range(10):
        base = 100 + i * 0.1
        h4.extend([_c(i * 10 + j, base, base + 1, base - 0.5, base + 0.3) for j in range(3)])
    h4_fvg_block = _bullish_fvg_at(500, low=100.0, gap=2.0)
    h4 = h4[:20] + h4_fvg_block + h4[23:]

    m15 = [_c(600 + i * 900, 106, 106.5, 105.5, 106) for i in range(5)]
    m15.append(_c(600 + 5 * 900, 106, 106.2, 101.5, 102.0))

    incremental = H4M15Engine(DEFAULT_H4_M15_CONFIG)
    incremental.bootstrap_h4("EURUSD", h4, atr_h4=2.0)

    for i in range(6):
        fresh = H4M15Engine(DEFAULT_H4_M15_CONFIG)
        fresh.bootstrap_h4("EURUSD", h4, atr_h4=2.0)
        for j in range(i + 1):
            fresh.process_m15_bar(m15[j], m15[: j + 1], 2.0)
        incremental.process_m15_bar(m15[i], m15[: i + 1], 2.0)
        assert {s.setup_id: s.state for s in incremental.all_setups()} == {
            s.setup_id: s.state for s in fresh.all_setups()
        }


def test_analyze_api_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    h4 = [_c(900 + i, 1.086, 1.087, 1.085, 1.086) for i in range(30)] + _bullish_fvg_at(
        1000, low=1.0840, gap=0.0010
    )
    m15 = [_c(2000 + i * 900, 1.086, 1.087, 1.085, 1.086) for i in range(10)]
    r = client.post(
        "/api/v1/h4-m15-fvg/analyze",
        json={"symbol": "EURUSD", "candles": {"H4": [c.__dict__ for c in h4], "M15": [c.__dict__ for c in m15]}, "persist": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["module"] == "h4_m15_fvg"
    assert data["advisory_only"] is True

def test_analyze_service_shape():
    clear_store()
    h4 = _bullish_fvg_at(1000, low=1.0840, gap=0.0010)
    pad_h4 = [_c(900 + i, 1.086, 1.087, 1.085, 1.086) for i in range(30)]
    m15 = [_c(2000 + i * 900, 1.086, 1.087, 1.085, 1.086) for i in range(10)]
    out = analyze_h4_m15_fvg(
        symbol="EURUSD",
        candles_h4=pad_h4 + h4,
        candles_m15=m15,
        persist=False,
    )
    assert out["module"] == "h4_m15_fvg"
    assert out["valid"] is True
    assert "setups" in out
    assert out["advisory_only"] is True


def test_clear_stale_exec_fvg_rejection():
    setup = H4M15Setup(
        setup_id="S1",
        symbol="XAUUSD",
        direction="BULLISH",
        state=H4M15SetupState.WAITING_FOR_RETRACE,
        htf_fvg=FvgZone(
            fvg_id="H4-1",
            direction="BULLISH",
            timeframe="H4",
            created_time=100,
            lower=100.0,
            upper=102.0,
            gap_size=2.0,
            gap_atr=0.5,
            displacement_score=50.0,
        ),
    )
    setup.rejections = [_EXEC_FVG_DIRECTION_MISMATCH, "Other note"]
    _clear_stale_exec_fvg_rejection(setup)
    assert setup.rejections == ["Other note"]
