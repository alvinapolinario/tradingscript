"""Unit tests for shared market_structure package."""
from __future__ import annotations

from app.market_structure import (
    Candle,
    atr,
    candles_from_payload,
    detect_fvgs,
    detect_mss,
    find_swings,
    htf_bias,
    premium_discount,
    score_displacement,
    try_invert_fvg,
    update_fvg_mitigation,
    validate_candles,
)
from app.market_structure.types import FvgStatus


class _FvgCfg:
    fvg_min_gap_atr = 0.05
    ifvg_min_break_atr = 0.05
    ifvg_require_body_close = True


class _MssCfg:
    displacement_min_body_atr = 0.8


def _c(t: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c)


def test_candle_validation_rejects_unsorted():
    candles = [_c(2, 1, 2, 0.5, 1.5), _c(1, 1, 2, 0.5, 1.5), _c(3, 1, 2, 0.5, 1.5)]
    assert validate_candles(candles) == "Unsorted candles"


def test_candles_from_payload_aliases():
    rows = [{"t": 1, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}]
    candles = candles_from_payload(rows)
    assert len(candles) == 1
    assert candles[0].time == 1
    assert candles[0].volume == 100.0


def test_atr_fallback_on_short_series():
    candles = [_c(1, 100, 101, 99, 100.5)]
    assert atr(candles) == 2.0


def test_bullish_fvg_detection():
    candles = [
        _c(1, 100, 101, 99, 100.5),
        _c(2, 100.5, 103, 100, 102.5),
        _c(3, 102.5, 105, 102, 104.5),
    ]
    fvgs = detect_fvgs(candles, timeframe="M5", atr=2.0, cfg=_FvgCfg())
    assert len(fvgs) == 1
    assert fvgs[0].direction == "BULLISH"
    assert fvgs[0].fvg_id == "FVG-B-M5-3"


def test_bearish_fvg_detection():
    candles = [
        _c(1, 105, 106, 104, 104.5),
        _c(2, 104.5, 105, 101, 102),
        _c(3, 102, 103, 98, 99),
    ]
    fvgs = detect_fvgs(candles, timeframe="M5", atr=2.0, cfg=_FvgCfg())
    assert len(fvgs) == 1
    assert fvgs[0].direction == "BEARISH"


def test_fvg_mitigation_partial_and_full():
    fvg = detect_fvgs(
        [_c(1, 100, 101, 99, 100.5), _c(2, 100.5, 103, 100, 102.5), _c(3, 102.5, 105, 102, 104.5)],
        timeframe="M5",
        atr=2.0,
        cfg=_FvgCfg(),
    )[0]
    update_fvg_mitigation(fvg, (fvg.lower + fvg.upper) / 2)
    assert fvg.mitigation_pct >= 50
    assert fvg.status in (FvgStatus.PARTIALLY_MITIGATED, FvgStatus.MIDPOINT_REACHED)
    update_fvg_mitigation(fvg, fvg.lower - 0.01)
    assert fvg.status == FvgStatus.FULLY_MITIGATED


def test_ifvg_inversion():
    candles = [
        _c(1, 100, 101, 99, 100.5),
        _c(2, 100.5, 103, 100, 102.5),
        _c(3, 102.5, 105, 102, 104.5),
        _c(4, 104.5, 105, 100, 100.8),
    ]
    fvg = detect_fvgs(candles[:3], timeframe="M5", atr=2.0, cfg=_FvgCfg())[0]
    assert try_invert_fvg(fvg, candles[3], 2.0, _FvgCfg())
    assert fvg.direction == "BEARISH"
    assert fvg.status == FvgStatus.INVERTED


def test_find_swings_confirmed_pivot():
    candles = [
        _c(1, 100, 101, 99, 100),
        _c(2, 101, 102, 100, 101),
        _c(3, 102, 105, 101, 104),
        _c(4, 104, 103, 100, 101),
        _c(5, 101, 102, 99, 100),
    ]
    swings = find_swings(candles, left=1, right=1, atr_val=1.0, min_atr=0.1)
    highs = [s for s in swings if s["type"] == "HIGH"]
    assert len(highs) == 1
    assert highs[0]["index"] == 2


def test_detect_mss_bearish():
    candles = [
        _c(1, 100, 101, 99, 100),
        _c(2, 99, 100, 97, 98),
        _c(3, 97, 98, 92, 92),
    ]
    swings = [{"type": "LOW", "price": 93.0, "time": 3, "index": 2}]
    mss = detect_mss(candles, swings, "BEARISH", 2.0, _MssCfg())
    assert mss is not None
    assert mss["direction"] == "BEARISH"
    assert mss["broken_level"] == 93.0


def test_premium_discount_zones():
    assert premium_discount(110.0, 90.0, 105.0) == "DEEP_PREMIUM"
    assert premium_discount(110.0, 90.0, 96.0) == "DISCOUNT"


def test_htf_bias():
    bull = [_c(i, 100 + i * 0.5, 101 + i * 0.5, 99 + i * 0.5, 100 + i * 0.5) for i in range(25)]
    assert htf_bias(bull) == "BULLISH"
    bear = [_c(i, 120 - i * 0.5, 121 - i * 0.5, 119 - i * 0.5, 120 - i * 0.5) for i in range(25)]
    assert htf_bias(bear) == "BEARISH"


def test_score_displacement():
    candle = _c(1, 100, 110, 99, 109)
    score = score_displacement(candle, atr=2.0, structure_break=True, fvg_created=True)
    assert score >= 50.0
