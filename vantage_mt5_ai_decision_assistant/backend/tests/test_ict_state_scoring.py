"""ICT state machine and scoring — Steps 6–7 tests."""
from __future__ import annotations

from app.analysis.ict import analyze_ict_strategy
from app.analysis.ict.scorer import decide_from_score, quality_band, score_ict_setup
from app.analysis.ict.state_machine import (
    check_expiration,
    check_invalidation,
    make_setup_id,
    merge_state,
)
from app.analysis.ict.state_store import clear_store, get_active_setup, list_setups
from app.analysis.ict.types import (
    DEFAULT_ICT_CONFIG,
    IctConfig,
    IctDecision,
    IctSetupContext,
    IctSetupState,
    LiquiditySweepEvent,
)
from app.market_structure.types import Candle


def _c(t: int, o: float, h: float, l: float, cl: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=cl)


def _sweep(bias: str = "BEARISH") -> LiquiditySweepEvent:
    return LiquiditySweepEvent(
        detected=True,
        sweep_type="BUY_SIDE" if bias == "BEARISH" else "SELL_SIDE",
        trade_bias=bias,
        level=4011.0,
        sweep_price=4012.5,
        sweep_time=1_700_038_700,
        penetration=1.5,
        closed_back_inside=True,
        quality_score=80.0,
    )


def _mini_bearish_series() -> tuple[list[Candle], list[Candle]]:
    """Compact bearish ICT fixture for persistence tests."""
    setup: list[Candle] = []
    base = 4000.0
    t = 1_700_000_000
    for i in range(40):
        setup.append(_c(t + i * 900, base, base + 8, base - 2, base + 1))
    bsl = base + 11.0
    setup.append(_c(t + 43 * 900, base + 8, bsl + 1.5, base + 7, base + 9.5))
    setup.append(_c(t + 44 * 900, base + 9, base + 10, base + 2, base + 3))
    setup.append(_c(t + 45 * 900, base + 3, base + 4, base - 1, base + 0.5))
    setup.append(_c(t + 46 * 900, base + 0.5, base + 1, base - 3, base - 2.5))
    et = t + 43 * 900
    exec_c = [
        _c(et, base + 9, bsl + 1.2, base + 8, base + 9.8),
        _c(et + 300, base + 9.5, base + 10, base + 5, base + 5.5),
        _c(et + 600, base + 5, base + 6, base + 4, base + 4.5),
        _c(et + 900, base + 4.5, base + 5, base + 1, base + 1.5),
        _c(et + 1200, base + 1.5, base + 2.5, base + 0.5, base + 2.0),
        _c(et + 1500, base + 2.0, base + 3.5, base + 1.8, base + 3.0),
    ]
    return setup, exec_c


def setup_function():
    clear_store()


def test_merge_state_never_regresses():
    assert merge_state(IctSetupState.MSS_CONFIRMED, IctSetupState.WAITING_FOR_DISPLACEMENT) == IctSetupState.MSS_CONFIRMED
    assert merge_state(IctSetupState.LIQUIDITY_SWEPT, IctSetupState.TRIGGERED) == IctSetupState.TRIGGERED
    assert merge_state(IctSetupState.TRIGGERED, IctSetupState.INVALIDATED) == IctSetupState.INVALIDATED
    # Forward progression allowed
    assert merge_state(IctSetupState.MSS_CONFIRMED, IctSetupState.WAITING_FOR_RETRACE) == IctSetupState.WAITING_FOR_RETRACE


def test_stable_setup_id_from_sweep():
    sid = make_setup_id("XAUUSD", "M15", _sweep(), "BEARISH")
    assert sid == "ICT-XAUUSD-M15-1700038700-S"
    assert sid == make_setup_id("XAUUSD", "M15", _sweep(), "BEARISH")


def test_expiration_after_max_age():
    cfg = IctConfig(max_setup_age_candles=5)
    ctx = IctSetupContext(trade_bias="BEARISH", state=IctSetupState.WAITING_FOR_MSS, sweep=_sweep())
    candles = [_c(1_700_038_700 + i * 900, 4000, 4001, 3999, 4000) for i in range(8)]
    assert check_expiration(ctx, candles, cfg) is True
    assert ctx.state == IctSetupState.EXPIRED


def test_invalidation_bearish_above_sl():
    cfg = IctConfig()
    ctx = IctSetupContext(trade_bias="BEARISH", state=IctSetupState.TRIGGERED, sweep=_sweep())
    candles = [_c(1, 4010, 4015, 4009, 4014)]
    assert check_invalidation(ctx, 4014, candles, cfg, 4013.0) is True
    assert ctx.state == IctSetupState.INVALIDATED


def test_scoring_gates_and_penalties():
    ctx = IctSetupContext(
        trade_bias="BEARISH",
        state=IctSetupState.WAITING_FOR_MSS,
        displacement_score=30.0,
        premium_discount_zone="DISCOUNT",
        htf_bias="BULLISH",
    )
    ctx.sweep = _sweep()
    score, components, gates, penalties = score_ict_setup(
        ctx,
        htf_confidence=70.0,
        htf_aligned=False,
        session_score=50.0,
        risk_reward=1.5,
        cfg=IctConfig(require_displacement=True, minimum_rr=2.0),
    )
    assert score <= 65.0  # lifecycle cap for WAITING_FOR_MSS
    assert gates["displacement"] is False
    assert any("countertrend" in p.lower() or "Missing required" in p for p in penalties)


def test_decide_from_score_triggered():
    gates = {"liquidity_sweep": True, "displacement": True, "mss": True, "fvg": True}
    d = decide_from_score(
        state=IctSetupState.TRIGGERED,
        score=80.0,
        risk_reward=2.5,
        gates=gates,
        htf_aligned=True,
        trade_bias="BEARISH",
        cfg=DEFAULT_ICT_CONFIG,
    )
    assert d == IctDecision.SELL


def test_quality_bands():
    assert quality_band(90) == "VERY HIGH"
    assert quality_band(75) == "HIGH"
    assert quality_band(55) == "MODERATE"
    assert quality_band(30) == "LOW"


def test_state_persistence_across_analyze_calls():
    setup, exec_c = _mini_bearish_series()
    cfg = IctConfig(min_candles=40, displacement_min_score=35.0, fvg_min_gap_atr=0.01)
    r1 = analyze_ict_strategy(symbol="XAUUSD", candles_setup=setup, candles_execution=exec_c, cfg=cfg)
    sid = r1["setup_id"]
    assert sid.startswith("ICT-XAUUSD-M15-")
    active = get_active_setup("XAUUSD", "M15")
    assert active is not None
    assert active.setup_id == sid
    r2 = analyze_ict_strategy(symbol="XAUUSD", candles_setup=setup, candles_execution=exec_c, cfg=cfg)
    assert r2["setup_id"] == sid
    assert "setup_record" in r2
    assert list_setups("XAUUSD")
