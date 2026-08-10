"""Box Theory — unit and integration tests."""
from __future__ import annotations

from app.analysis.box_theory.breakout import detect_breakout
from app.analysis.box_theory.detector import detect_box
from app.analysis.box_theory.fakeout import detect_fakeout
from app.analysis.box_theory.retest import detect_retest
from app.analysis.box_theory.risk import calculate_risk_plan
from app.analysis.box_theory.scorer import score_signal
from app.analysis.box_theory.service import analyze_box_strategy
from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig, Candle
from app.analysis.box_theory.utils import atr
from app.box_discord_notify import _dedupe_send


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def _consolidation(t0: int = 1_000, n: int = 20, hi: float = 3400.0, lo: float = 3380.0) -> list[Candle]:
    out: list[Candle] = []
    mid = (hi + lo) / 2.0
    for i in range(n):
        if i % 4 == 0:
            out.append(_c(t0 + i, mid, hi, lo + 4, hi - 0.5))
        elif i % 4 == 1:
            out.append(_c(t0 + i, mid, hi - 4, lo, lo + 0.5))
        elif i % 4 == 2:
            out.append(_c(t0 + i, mid, hi - 2, lo + 2, mid))
        else:
            out.append(_c(t0 + i, mid, hi - 1, lo + 1, mid + 1))
    return out


def _cfg(**kwargs) -> BoxStrategyConfig:
    base = {
        "lookback_candles": 12,
        "min_box_candles": 8,
        "min_touches": 2,
        "minimum_signal_score": 50.0,
        "require_retest": True,
        "min_inside_ratio": 0.55,
    }
    base.update(kwargs)
    return BoxStrategyConfig(**base)


def test_valid_box_detection():
    candles = _consolidation()
    cfg = _cfg()
    box = detect_box(candles, cfg, atr(candles))
    assert box is not None
    assert box.upper_touches >= 2
    assert box.lower_touches >= 2
    assert box.high >= 3395
    assert box.low <= 3385


def test_invalid_box_too_wide():
    candles = [_c(i, 3000, 3200, 2800, 3100) for i in range(20)]
    cfg = _cfg(max_box_height_atr=0.5)
    assert detect_box(candles, cfg, atr(candles)) is None


def test_bullish_breakout():
    candles = _consolidation()
    cfg = _cfg()
    box = detect_box(candles, cfg, atr(candles))
    assert box is not None
    atr_v = atr(candles)
    buf = cfg.breakout_buffer_atr * atr_v
    close = box.high + buf + 1.0
    breakout_candle = _c(box.end_time + 60, box.high, close + 2, box.high - 1, close)
    br = detect_breakout(box, candles + [breakout_candle], cfg, atr_v)
    assert br is not None
    assert br.direction == "UP"
    assert br.wick_only is False


def test_wick_only_not_breakout():
    candles = _consolidation()
    cfg = _cfg()
    box = detect_box(candles, cfg, atr(candles))
    wick = _c(box.end_time + 60, box.high - 1, box.high + 8, box.high - 2, box.high - 0.5)
    assert detect_breakout(box, candles + [wick], cfg, atr(candles)) is None


def test_bull_trap():
    candles = _consolidation()
    cfg = _cfg()
    box = detect_box(candles, cfg, atr(candles))
    trap = _c(box.end_time + 60, box.high - 0.5, box.high + 6, box.high - 2, box.high - 1)
    fake = detect_fakeout(box, candles + [trap], box.end_time)
    assert fake is not None
    assert fake.trap == "BULL_TRAP"


def test_bear_trap():
    candles = _consolidation()
    cfg = _cfg()
    box = detect_box(candles, cfg, atr(candles))
    trap = _c(box.end_time + 60, box.low + 0.5, box.low + 2, box.low - 6, box.low + 1)
    fake = detect_fakeout(box, candles + [trap], box.end_time)
    assert fake is not None
    assert fake.trap == "BEAR_TRAP"


def test_successful_bullish_retest():
    candles = _consolidation()
    cfg = _cfg(retest_tolerance_atr=0.5)
    box = detect_box(candles, cfg, atr(candles))
    atr_v = atr(candles)
    buf = cfg.breakout_buffer_atr * atr_v
    close = box.high + buf + 1.0
    br = detect_breakout(
        box,
        candles + [_c(box.end_time + 60, box.high, close + 2, box.high - 1, close)],
        cfg,
        atr_v,
    )
    assert br is not None
    retest = _c(box.end_time + 120, box.high - 0.4, box.high + 1.2, box.high - 0.6, box.high + 0.6)
    rt = detect_retest(box, br, [retest], cfg, atr_v)
    assert rt.detected
    assert rt.confirmed


def test_confidence_scoring():
    box = BoxRange("x", 3400, 3380, 3390, 20, 1, 100, 12, 3, 3, 0.8, 70)
    from app.analysis.box_theory.breakout import BreakoutEvent
    from app.analysis.box_theory.liquidity import LiquiditySweep
    from app.analysis.box_theory.retest import RetestEvent

    br = BreakoutEvent("UP", 3402.5, 200, 0.7, True, False)
    rt = RetestEvent(True, True, 3400.4, 260, 2)
    sweep = LiquiditySweep(True, "SELL_SIDE", 3378, 50, 3380)
    score, quality, reasons = score_signal(
        box=box,
        breakout=br,
        retest=rt,
        sweep=sweep,
        fvg_confirmed=True,
        htf="BULLISH",
        atr_expansion=True,
        volume_confirmed=True,
        cfg=_cfg(),
    )
    assert score >= 70
    assert quality.value in ("HIGH", "VERY_HIGH")
    assert reasons


def test_risk_reward_calculation():
    box = BoxRange("x", 3400, 3380, 3390, 20, 1, 100, 12, 3, 3, 0.8, 70)
    from app.analysis.box_theory.breakout import BreakoutEvent
    from app.analysis.box_theory.retest import RetestEvent

    br = BreakoutEvent("UP", 3402.5, 200, 0.7, True, False)
    rt = RetestEvent(True, True, 3400.4, 260, 2)
    plan = calculate_risk_plan(box=box, breakout=br, retest=rt, cfg=_cfg(), atr_val=2.0)
    assert plan["entry"] > 0
    assert plan["stop_loss"] < plan["entry"]
    assert plan["tp1"] > plan["entry"]
    assert plan["risk_reward"] > 0


def test_analyze_box_strategy_integration():
    candles = _consolidation(n=20)
    cfg = _cfg(minimum_signal_score=40.0, require_retest=False)
    box = detect_box(candles, cfg, atr(candles))
    assert box is not None
    breakout = _c(box.end_time + 60, box.high, box.high + 5, box.high - 1, box.high + 3)
    all_c = candles + [breakout]
    r = analyze_box_strategy(symbol="XAUUSD", candles_box=all_c, cfg=cfg)
    assert r["valid"] is True
    assert r["strategy"] == "BOX_THEORY"
    assert "box_status" in r


def test_non_gold_symbol_disabled():
    r = analyze_box_strategy(symbol="EURUSD", candles_box=[_c(1, 1, 2, 0.5, 1.5)] * 20)
    assert r["valid"] is False


def test_duplicate_discord_prevention(monkeypatch):
    monkeypatch.setattr("app.box_discord_notify.box_discord_configured", lambda _st=None: True)
    monkeypatch.setattr("app.box_discord_notify._send_embed", lambda **kwargs: (True, "sent"))
    sid = "XAUUSD|1|2|BUY|BUY_CONFIRMED"
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is True
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is False
