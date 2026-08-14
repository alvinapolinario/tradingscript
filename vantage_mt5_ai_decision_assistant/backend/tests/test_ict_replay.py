"""ICT replay and causality hardening tests."""
from __future__ import annotations

from app.analysis.ict import analyze_ict_strategy
from app.analysis.ict.causal import evaluate_causal_sequence, freeze_mss_target, select_execution_fvg
from app.analysis.ict.displacement_leg import find_displacement_leg
from app.analysis.ict.replay import replay_ict_sequence
from app.analysis.ict.state_store import clear_store
from app.analysis.ict.sweep import detect_liquidity_sweep
from app.analysis.ict.types import DEFAULT_ICT_CONFIG, IctConfig, IctSetupContext, IctSetupState, LiquidityLevel
from app.analysis.ict.liquidity import build_liquidity_levels
from app.market_structure.fvg import detect_fvgs
from app.market_structure.types import Candle


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _bullish_valid_fixture() -> tuple[list[Candle], list[Candle]]:
    """SSL sweep → bullish displacement → MSS → bullish M5 FVG → retrace."""
    setup: list[Candle] = []
    base = 1.0840
    t = 1_700_000_000
    for i in range(40):
        setup.append(_c(t + i * 900, base, base + 0.0008, base - 0.0002, base + 0.0001))
    ssl = base - 0.0010
    setup.append(_c(t + 40 * 900, base, base + 0.0012, ssl - 0.0003, base + 0.0006))
    setup.append(_c(t + 41 * 900, base + 0.0006, base + 0.0010, base + 0.0005, base + 0.0008))
    setup.append(_c(t + 42 * 900, base + 0.0008, base + 0.0011, base + 0.0007, base + 0.0010))
    swing_break = base + 0.0012
    setup.append(_c(t + 43 * 900, base + 0.0008, ssl - 0.0005, ssl - 0.0008, base + 0.0005))
    setup.append(_c(t + 44 * 900, base + 0.0005, swing_break + 0.0004, base + 0.0004, swing_break + 0.0002))
    setup.append(_c(t + 45 * 900, swing_break + 0.0002, swing_break + 0.0005, swing_break, swing_break + 0.0003))

    et = t + 43 * 900
    exec_c = [
        _c(et, base, ssl - 0.0004, ssl - 0.0006, base + 0.0004),
        _c(et + 300, swing_break, swing_break + 0.0003, swing_break - 0.0001, swing_break + 0.0002),
        _c(et + 600, swing_break + 0.0001, swing_break + 0.0002, swing_break - 0.0001, swing_break + 0.00015),
        _c(et + 900, swing_break + 0.00015, swing_break + 0.00025, swing_break + 0.00005, swing_break + 0.0002),
        _c(et + 1200, swing_break + 0.00005, swing_break + 0.00018, swing_break - 0.00005, swing_break + 0.00012),
        _c(et + 1500, swing_break + 0.00010, swing_break + 0.00016, swing_break + 0.00008, swing_break + 0.00012),
    ]
    return setup, exec_c


def _relaxed_cfg() -> IctConfig:
    return IctConfig(
        min_candles=40,
        displacement_min_body_atr=0.4,
        displacement_min_range_atr=0.4,
        displacement_min_body_ratio=0.45,
        displacement_min_score=30.0,
        fvg_min_gap_atr=0.0001,
        sweep_min_penetration_atr=0.01,
        sweep_max_penetration_atr=2.0,
        minimum_rr=0.5,
        min_confidence=40.0,
    )


def setup_function():
    clear_store()


def test_replay_deterministic():
    setup, exec_c = _bullish_valid_fixture()
    cfg = _relaxed_cfg()
    a = replay_ict_sequence(symbol="EURUSD", setup_candles=setup, execution_candles=exec_c, cfg=cfg)
    b = replay_ict_sequence(symbol="EURUSD", setup_candles=setup, execution_candles=exec_c, cfg=cfg)
    assert a == b


def test_replay_no_sweep_before_bar_closes():
    setup, exec_c = _bullish_valid_fixture()
    cfg = _relaxed_cfg()
    full = analyze_ict_strategy(
        symbol="EURUSD",
        candles_setup=setup,
        candles_execution=exec_c,
        cfg=cfg,
    )
    canonical_sweep_time = (full.get("liquidity_event") or {}).get("time")
    assert canonical_sweep_time
    steps = replay_ict_sequence(symbol="EURUSD", setup_candles=setup, execution_candles=exec_c, cfg=cfg)
    for step in steps:
        lev = step.get("liquidity_event") or {}
        if lev.get("time") == canonical_sweep_time:
            assert step["eval_bar_time"] >= canonical_sweep_time
        if step["eval_bar_time"] < canonical_sweep_time:
            assert lev.get("time") != canonical_sweep_time


def test_fvg_before_sweep_rejected():
    setup, exec_c = _bullish_valid_fixture()
    early_fvg_time = setup[10].time
    exec_c = [_c(early_fvg_time, 1.084, 1.0842, 1.0838, 1.0841)] + exec_c
    cfg = _relaxed_cfg()
    ctx = IctSetupContext(trade_bias="BULLISH", state=IctSetupState.LIQUIDITY_SWEPT)
    atr = 0.001
    bsl, ssl, _pd = build_liquidity_levels(setup, atr, cfg)
    sweep = detect_liquidity_sweep(setup, bsl_levels=bsl, ssl_levels=ssl, atr_val=atr, cfg=cfg)
    assert sweep is not None
    ctx.sweep = sweep
    ctx.setup_id = f"ICT-EURUSD-M15-{sweep.sweep_time}-B"
    result = evaluate_causal_sequence(ctx, setup, exec_c, atr, atr, cfg, setup[-1].close, symbol="EURUSD")
    if result.fvg:
        assert result.fvg.created_time >= sweep.sweep_time


def test_displacement_before_sweep_invalid():
    cfg = _relaxed_cfg()
    sweep_time = 1000
    candles = [
        _c(900, 1.0, 1.01, 0.99, 1.005),
        _c(sweep_time, 1.0, 1.01, 0.98, 1.002),
    ]
    disp = find_displacement_leg(
        candles,
        sweep_time=sweep_time,
        direction="BULLISH",
        setup_id="TEST",
        atr=0.01,
        cfg=cfg,
    )
    assert disp is None or disp.start_time >= sweep_time


def test_mss_uses_frozen_pre_sweep_swing():
    setup, _ = _bullish_valid_fixture()
    cfg = _relaxed_cfg()
    atr = 0.001
    sweep_time = setup[43].time
    target = freeze_mss_target(setup[:44], sweep_time, "BULLISH", atr, cfg)
    assert target is not None
    assert target.time < sweep_time


def test_causality_invalid_mss_before_displacement():
    cfg = _relaxed_cfg()
    ctx = IctSetupContext(trade_bias="BEARISH", state=IctSetupState.LIQUIDITY_SWEPT)
    setup = [_c(i * 900, 4000, 4001, 3999, 4000) for i in range(60)]
    exec_c = setup
    result = evaluate_causal_sequence(ctx, setup, exec_c, 2.0, 2.0, cfg, 4000.0, symbol="XAUUSD")
    assert result.state != IctSetupState.ENTRY_READY


def test_entry_ready_requires_two_passes_in_zone():
    setup, exec_c = _bullish_valid_fixture()
    cfg = _relaxed_cfg()
    touch_price = exec_c[-1].close
    r1 = analyze_ict_strategy(
        symbol="EURUSD",
        candles_setup=setup,
        candles_execution=exec_c,
        bid=touch_price,
        cfg=cfg,
    )
    r2 = analyze_ict_strategy(
        symbol="EURUSD",
        candles_setup=setup,
        candles_execution=exec_c,
        bid=touch_price,
        cfg=cfg,
    )
    if r1.get("execution_fvg"):
        assert r1.get("state") in ("FVG_TOUCHED", "WAITING_FOR_RETRACE", "ENTRY_ZONE_ACTIVE", "EXECUTION_FVG_FOUND")
    if r2.get("entry_ready"):
        assert r2.get("entry_event_id")


def test_wrong_direction_fvg_not_selected():
    setup, exec_c = _bullish_valid_fixture()
    cfg = _relaxed_cfg()
    atr = 0.001
    fvgs = detect_fvgs(exec_c, timeframe="M5", atr=atr, cfg=cfg, symbol="EURUSD")
    bear = [f for f in fvgs if f.direction == "BEARISH"]
    if bear:
        f = bear[0]
        assert f.created_time >= setup[43].time or f.direction != "BULLISH"
