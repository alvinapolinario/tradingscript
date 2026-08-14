"""ICT Phase 4 — OTE, order blocks, breaker confluence."""
from __future__ import annotations

from app.analysis.ict import analyze_ict_strategy
from app.analysis.ict.poi import (
    apply_poi_analysis,
    compute_impulse_ote,
    find_causal_order_block,
    zones_overlap,
)
from app.analysis.ict.scorer import score_ict_setup
from app.analysis.ict.types import DEFAULT_ICT_CONFIG, DisplacementEvent, IctConfig, IctSetupContext, IctSetupState
from app.market_structure.types import Candle


def _c(t, o, h, l, cl):
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _disp_bullish() -> DisplacementEvent:
    return DisplacementEvent(
        event_id="DISP-1",
        setup_id="ICT-TEST",
        direction="BULLISH",
        start_time=200,
        end_time=200,
        primary_candle_time=200,
        open_price=1.0,
        close_price=1.02,
        high=1.025,
        low=0.995,
        body_size=0.02,
        range_size=0.03,
        atr=0.01,
        body_atr_ratio=2.0,
        range_atr_ratio=3.0,
        body_to_range_ratio=0.66,
        close_location=0.8,
        distance_travelled=0.02,
        distance_atr=2.0,
        bars_count=1,
        structure_break=True,
        fvg_created=False,
        quality_score=72.0,
    )


def test_zones_overlap():
    assert zones_overlap(1.0, 1.1, 1.05, 1.15)
    assert not zones_overlap(1.0, 1.05, 1.06, 1.10)


def test_impulse_ote_bullish():
    disp = _disp_bullish()
    ote = compute_impulse_ote(disp, "BULLISH", price=1.012, cfg=DEFAULT_ICT_CONFIG)
    assert ote["ote_valid"]
    assert ote["ote_low"] < ote["ote_mid"] < ote["ote_high"]
    assert ote["ote_high"] <= disp.high
    assert ote["ote_low"] >= disp.low


def test_causal_order_block_bullish():
    t = 100
    candles = [
        _c(t, 1.00, 1.01, 0.99, 1.005),
        _c(t + 100, 1.005, 1.008, 0.998, 1.000),  # bearish origin
        _c(t + 200, 1.000, 1.025, 0.995, 1.020),  # bullish displacement
    ]
    disp = _disp_bullish()
    disp.start_time = t + 200
    disp.end_time = t + 200
    ob = find_causal_order_block(
        candles,
        displacement=disp,
        sweep_time=t,
        direction="BULLISH",
        setup_id="ICT-TEST",
        atr=0.01,
        cfg=DEFAULT_ICT_CONFIG,
    )
    assert ob is not None
    assert ob.direction == "BULLISH"
    assert ob.lower == candles[1].low
    assert ob.upper == candles[1].high
    assert ob.with_sweep


def test_apply_poi_analysis_populates_context():
    ctx = IctSetupContext(trade_bias="BULLISH", state=IctSetupState.DISPLACEMENT_CONFIRMED)
    ctx.setup_id = "ICT-TEST"
    ctx.displacement_event = _disp_bullish()
    from app.analysis.ict.types import LiquiditySweepEvent

    ctx.sweep = LiquiditySweepEvent(
        detected=True,
        sweep_type="SELL_SIDE",
        trade_bias="BULLISH",
        level=0.99,
        sweep_price=0.988,
        sweep_time=100,
        penetration=0.002,
        closed_back_inside=True,
    )
    candles = [
        _c(100, 1.0, 1.01, 0.99, 1.005),
        _c(150, 1.005, 1.008, 0.998, 1.000),
        _c(200, 1.0, 1.025, 0.995, 1.02),
    ]
    apply_poi_analysis(ctx, candles, price=1.012, atr_setup=0.01, cfg=DEFAULT_ICT_CONFIG)
    assert ctx.ote_valid
    assert ctx.order_block is not None


def test_scorer_ote_confluence_bonus():
    ctx = IctSetupContext(trade_bias="BULLISH", state=IctSetupState.WAITING_FOR_RETRACE)
    ctx.ote_valid = True
    ctx.price_in_ote = True
    ctx.order_block = find_causal_order_block(
        [
            _c(100, 1.0, 1.01, 0.99, 1.005),
            _c(150, 1.005, 1.008, 0.998, 1.0),
            _c(200, 1.0, 1.025, 0.995, 1.02),
        ],
        displacement=_disp_bullish(),
        sweep_time=100,
        direction="BULLISH",
        setup_id="ICT-TEST",
        atr=0.01,
        cfg=DEFAULT_ICT_CONFIG,
    )
    score_with, _, _, _ = score_ict_setup(
        ctx, htf_confidence=80, htf_aligned=True, session_score=70, risk_reward=2.5, cfg=DEFAULT_ICT_CONFIG,
    )
    ctx.price_in_ote = False
    ctx.order_block = None
    ctx.ote_valid = False
    score_without, _, _, _ = score_ict_setup(
        ctx, htf_confidence=80, htf_aligned=True, session_score=70, risk_reward=2.5, cfg=DEFAULT_ICT_CONFIG,
    )
    assert score_with > score_without


def test_analyze_payload_includes_poi():
    setup, exec_c = _bearish_fixture()
    cfg = IctConfig(
        min_candles=40,
        displacement_min_body_atr=0.4,
        displacement_min_range_atr=0.4,
        displacement_min_body_ratio=0.45,
        displacement_min_score=30.0,
        fvg_min_gap_atr=0.0001,
        sweep_min_penetration_atr=0.01,
        minimum_rr=0.5,
        min_confidence=40.0,
    )
    out = analyze_ict_strategy(symbol="XAUUSD", candles_setup=setup, candles_execution=exec_c, cfg=cfg)
    assert "ote" in out
    assert "order_block" in out
    assert "poi_confluence" in out
    if out.get("displacement_event"):
        assert out["ote"]["valid"] or out["ote"]["ote_low"] == 0.0


def _bearish_fixture():
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
    exec_c = [
        _c(et, base + 9, bsl_level + 1.2, base + 8, base + 9.8),
        _c(et + 300, base + 9.5, base + 10, base + 5, base + 5.5),
        _c(et + 600, base + 5, base + 6, base + 4, base + 4.5),
        _c(et + 900, base + 4.5, base + 5, base + 1, base + 1.5),
        _c(et + 1200, base + 1.5, base + 2.5, base + 0.5, base + 2.0),
        _c(et + 1500, base + 2.0, base + 3.5, base + 1.8, base + 3.0),
    ]
    return setup, exec_c
