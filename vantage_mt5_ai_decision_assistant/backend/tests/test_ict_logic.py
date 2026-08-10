"""ICT strategy — unit and integration tests."""
from __future__ import annotations

from app.analysis.ict import analyze_ict_strategy
from app.analysis.ict.liquidity import build_liquidity_levels
from app.analysis.ict.scorer import score_ict_setup
from app.analysis.ict.sweep import detect_liquidity_sweep
from app.analysis.ict.types import DEFAULT_ICT_CONFIG, IctConfig, IctDecision, IctSetupContext, IctSetupState
from app.market_structure.types import Candle


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _bearish_ict_series() -> tuple[list[Candle], list[Candle]]:
    """Craft M15 setup + M5 execution series with BSL sweep → bearish ICT path."""
    setup: list[Candle] = []
    base = 4000.0
    t = 1_700_000_000
    # Consolidation — build swing high near 4010
    for i in range(40):
        setup.append(_c(t + i * 900, base, base + 8, base - 2, base + 1))
    # Explicit swing high region
    setup.append(_c(t + 40 * 900, base + 5, base + 12, base + 4, base + 6))
    setup.append(_c(t + 41 * 900, base + 6, base + 10, base + 5, base + 7))
    setup.append(_c(t + 42 * 900, base + 7, base + 11, base + 6, base + 8))
    bsl_level = base + 11.0
    # BSL sweep — pierce above 4011, close back below
    setup.append(_c(t + 43 * 900, base + 8, bsl_level + 1.5, base + 7, base + 9.5))
    # Bearish displacement
    setup.append(_c(t + 44 * 900, base + 9, base + 10, base + 2, base + 3))
    setup.append(_c(t + 45 * 900, base + 3, base + 4, base - 1, base + 0.5))
    setup.append(_c(t + 46 * 900, base + 0.5, base + 1, base - 3, base - 2.5))

    exec_candles: list[Candle] = []
    et = t + 43 * 900
    exec_candles.append(_c(et, base + 9, bsl_level + 1.2, base + 8, base + 9.8))
    exec_candles.append(_c(et + 300, base + 9.5, base + 10, base + 5, base + 5.5))
    # Bearish FVG: c1 high, c2 dump, c3 gap
    exec_candles.append(_c(et + 600, base + 5, base + 6, base + 4, base + 4.5))
    exec_candles.append(_c(et + 900, base + 4.5, base + 5, base + 1, base + 1.5))
    exec_candles.append(_c(et + 1200, base + 1.5, base + 2.5, base + 0.5, base + 2.0))
    # Retrace into FVG zone
    exec_candles.append(_c(et + 1500, base + 2.0, base + 3.5, base + 1.8, base + 3.0))

    return setup, exec_candles


def test_non_gold_symbol_disabled():
    r = analyze_ict_strategy(symbol="EURUSD", candles_setup=[_c(1, 1, 2, 0.5, 1.5)] * 20)
    assert r["valid"] is False


def test_liquidity_levels_from_swings():
    candles = [_c(i, 100, 101 + (i % 3), 99, 100) for i in range(30)]
    bsl, ssl = build_liquidity_levels(candles, 2.0, DEFAULT_ICT_CONFIG)
    assert isinstance(bsl, list)
    assert isinstance(ssl, list)


def test_sweep_detection_bsl():
    cfg = IctConfig(sweep_min_penetration_atr=0.05, sweep_max_penetration_atr=1.0)
    from app.analysis.ict.types import LiquidityLevel

    levels = [LiquidityLevel("BSL", 4011.0, 1000)]
    candles = [_c(1001, 4010, 4012.5, 4009, 4010.5)]
    sweep = detect_liquidity_sweep(candles, bsl_levels=levels, ssl_levels=[], atr_val=2.0, cfg=cfg)
    assert sweep is not None
    assert sweep.trade_bias == "BEARISH"
    assert sweep.sweep_type == "BUY_SIDE"


def test_bearish_ict_analyze_integration():
    setup, exec_c = _bearish_ict_series()
    cfg = IctConfig(
        min_candles=40,
        displacement_min_score=35.0,
        min_confidence=50.0,
        minimum_rr=1.0,
        fvg_min_gap_atr=0.01,
    )
    r = analyze_ict_strategy(
        symbol="XAUUSD",
        candles_setup=setup,
        candles_execution=exec_c,
        bid=setup[-1].close,
        cfg=cfg,
    )
    assert r["valid"] is True
    assert r["liquidity"]["sweep_detected"] is True
    assert r["htf_bias"]["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert "score_components" in r
    assert r["setup_id"].startswith("ICT-XAUUSD")
    assert r["status"] in [s.value for s in IctSetupState]


def test_scoring_components_sum():
    ctx = IctSetupContext(
        trade_bias="BEARISH",
        state=IctSetupState.MSS_CONFIRMED,
        displacement_score=70.0,
        premium_discount_zone="PREMIUM",
    )
    from app.analysis.ict.types import LiquiditySweepEvent

    ctx.sweep = LiquiditySweepEvent(
        detected=True,
        sweep_type="BUY_SIDE",
        trade_bias="BEARISH",
        level=4011.0,
        sweep_price=4012.5,
        sweep_time=1,
        penetration=1.5,
        closed_back_inside=True,
        quality_score=80.0,
    )
    ctx.mss = {"shift_detected": True, "direction": "BEARISH", "quality_score": 75.0}
    score, components, gates, penalties = score_ict_setup(
        ctx,
        htf_confidence=80.0,
        htf_aligned=True,
        session_score=70.0,
        risk_reward=2.5,
        cfg=DEFAULT_ICT_CONFIG,
    )
    assert 0 <= score <= 100
    assert components["liquidity_sweep"] > 0
    assert components["mss"] > 0
    assert isinstance(gates, dict)
