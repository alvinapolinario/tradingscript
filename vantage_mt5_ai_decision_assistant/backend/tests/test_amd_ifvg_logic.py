"""AMD + iFVG — unit and integration tests."""
from __future__ import annotations

from app.analysis.amd_ifvg_logic import (
    AmdIfvgConfig,
    Candle,
    analyze_amd_ifvg,
    detect_accumulation,
    detect_fvgs,
    detect_manipulation,
    try_invert_fvg,
)


def _c(t: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c)


def test_bullish_fvg_detection():
    candles = [
        _c(1, 100, 101, 99, 100.5),
        _c(2, 100.5, 103, 100, 102.5),
        _c(3, 102.5, 105, 102, 104.5),
    ]
    atr = 2.0
    fvgs = detect_fvgs(candles, timeframe="M5", atr=atr, cfg=AmdIfvgConfig(fvg_min_gap_atr=0.05))
    assert len(fvgs) == 1
    assert fvgs[0].direction == "BULLISH"


def test_bullish_fvg_inversion_to_bearish_ifvg():
    candles = [
        _c(1, 100, 101, 99, 100.5),
        _c(2, 100.5, 103, 100, 102.5),
        _c(3, 102.5, 105, 102, 104.5),
        _c(4, 104.5, 105, 100, 100.8),
    ]
    atr = 2.0
    cfg = AmdIfvgConfig(ifvg_min_break_atr=0.05)
    fvgs = detect_fvgs(candles[:3], timeframe="M5", atr=atr, cfg=cfg)
    f = fvgs[0]
    assert try_invert_fvg(f, candles[3], atr, cfg)
    assert f.direction == "BEARISH"


def test_accumulation_and_manipulation():
    candles = []
    base = 4000.0
    for i in range(10):
        candles.append(_c(i, base, base + 1.0, base - 1.0, base))
    candles.append(_c(10, base + 0.5, base + 2.5, base - 0.2, base + 0.3))
    acc = detect_accumulation(candles[:-1], 2.0, AmdIfvgConfig(accumulation_min_candles=8))
    assert acc is not None
    manip = detect_manipulation(acc, candles, 2.0, AmdIfvgConfig())
    assert manip is not None


def test_unsupported_symbol_disabled():
    r = analyze_amd_ifvg(symbol="GBPUSD", candles_setup=[_c(1, 1, 2, 0.5, 1.5)] * 20)
    assert r["valid"] is False


def test_eurusd_symbol_enabled():
    r = analyze_amd_ifvg(symbol="EURUSD", candles_setup=[_c(1, 1, 2, 0.5, 1.5)] * 20)
    assert r["valid"] is True
    assert r["gold_symbol_valid"] is True
