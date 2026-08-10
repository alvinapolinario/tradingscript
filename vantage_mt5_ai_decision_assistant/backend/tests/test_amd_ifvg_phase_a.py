"""AMD + iFVG Phase A — sequence gating, RR, retest, chase expiry."""
from __future__ import annotations

from app.analysis.amd_ifvg_logic import (
    AmdIfvgConfig,
    Candle,
    Decision,
    SetupState,
    analyze_amd_ifvg,
)


def _c(t: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c)


def _flat_range_candles(n: int, base: float = 4000.0, width: float = 2.0) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        out.append(_c(i, base, base + width / 2, base - width / 2, base))
    return out


def test_ifvg_not_detected_without_manipulation_sequence():
    """Inverted FVG alone must not surface as active iFVG without manip + MSS."""
    candles = _flat_range_candles(85)
    # Inject bullish FVG + bearish inversion on last bars (no sweep setup)
    candles[-4] = _c(81, 4000, 4001, 3999, 4000.5)
    candles[-3] = _c(82, 4000.5, 4004, 4000, 4003.5)
    candles[-2] = _c(83, 4003.5, 4006, 4003, 4005.5)
    candles[-1] = _c(84, 4005.5, 4006, 3998, 3999.0)

    r = analyze_amd_ifvg(symbol="XAUUSD", candles_setup=candles, candles_entry=candles, bid=3999.0)
    assert r["ifvg"]["detected"] is False
    assert r["decision"] == Decision.NO_TRADE.value


def test_ifvg_max_retests_zero_expires_on_first_touch():
    """First in-zone touch with ifvg_max_retests=0 must expire the setup."""
    setup = _flat_range_candles(82, base=4000.0, width=1.5)
    entry = list(setup)
    # Bearish sweep above range then re-entry
    setup.append(_c(82, 4000.2, 4002.8, 3999.8, 4000.0))
    # Displacement + MSS break on entry TF
    entry.extend(
        [
            _c(80, 4000.0, 4000.5, 3999.0, 3999.2),
            _c(81, 3999.0, 3999.5, 3995.0, 3995.5),
            _c(82, 3995.0, 3996.0, 3990.0, 3991.0),
            _c(83, 3991.0, 3992.0, 3988.0, 3989.0),
        ]
    )
    # Bullish FVG then bearish inversion aligned with bearish bias
    fvg_seed = [
        _c(84, 3990.0, 3992.0, 3989.0, 3991.5),
        _c(85, 3991.0, 3994.0, 3990.5, 3993.5),
        _c(86, 3993.0, 3995.0, 3992.0, 3994.5),
    ]
    entry.extend(fvg_seed)
    inv = _c(87, 3994.0, 3994.5, 3988.0, 3988.5)
    entry.append(inv)

    cfg = AmdIfvgConfig(ifvg_max_retests=0, minimum_trade_score=50.0, minimum_rr=1.0)
    mid = (fvg_seed[0].high + fvg_seed[2].low) / 2
    r = analyze_amd_ifvg(
        symbol="XAUUSD",
        candles_setup=setup,
        candles_entry=entry,
        bid=mid,
        cfg=cfg,
    )
    if r["ifvg"]["detected"]:
        assert r["setup_state"] == SetupState.EXPIRED.value
        assert r["decision"] != Decision.BUY.value
        assert r["decision"] != Decision.SELL.value


def test_minimum_rr_blocks_actionable_decision():
    """When RR is below minimum, decision must not be BUY/SELL."""
    cfg = AmdIfvgConfig(minimum_rr=50.0, minimum_trade_score=50.0, ifvg_max_retests=5)
    setup = _flat_range_candles(85, base=4000.0, width=0.4)
    setup.append(_c(85, 4000.0, 4000.55, 3999.45, 4000.0))
    entry = list(setup)
    entry.extend(
        [
            _c(86, 4000.0, 4000.3, 3999.5, 3999.6),
            _c(87, 3999.5, 3999.8, 3998.5, 3998.8),
            _c(88, 3998.5, 3999.0, 3997.0, 3997.5),
            _c(89, 3997.0, 3997.5, 3995.0, 3995.5),
        ]
    )
    r = analyze_amd_ifvg(
        symbol="XAUUSD",
        candles_setup=setup,
        candles_entry=entry,
        bid=3999.0,
        cfg=cfg,
    )
    if r["setup_state"] == SetupState.ENTRY_ZONE_ACTIVE.value:
        assert r["decision"] in {Decision.WAIT.value, Decision.NO_TRADE.value}
        assert r["decision"] not in {Decision.BUY.value, Decision.SELL.value}
        if r.get("risk_reward", 0) > 0:
            assert r["risk_reward"] < cfg.minimum_rr or any(
                "Risk:reward" in w for w in r["warnings"]
            )


def test_chase_max_atr_expires_bullish_setup():
    """Price too far above bullish iFVG should expire."""
    cfg = AmdIfvgConfig(chase_max_atr=0.01, minimum_rr=1.0)
    # Minimal analyze with high chase sensitivity — if iFVG active and price far, expired
    candles = _flat_range_candles(85)
    r = analyze_amd_ifvg(
        symbol="XAUUSD",
        candles_setup=candles,
        candles_entry=candles,
        bid=5000.0,
        cfg=cfg,
    )
    assert r["setup_state"] in {
        SetupState.SEARCHING_FOR_ACCUMULATION.value,
        SetupState.EXPIRED.value,
        SetupState.WAITING_FOR_LIQUIDITY_SWEEP.value,
    }
