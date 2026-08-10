"""Confidence scoring for Box Theory signals."""
from __future__ import annotations

from app.analysis.box_theory.breakout import BreakoutEvent
from app.analysis.box_theory.liquidity import LiquiditySweep
from app.analysis.box_theory.retest import RetestEvent
from app.analysis.box_theory.types import BoxRange, BoxStrategyConfig, SignalQuality
from app.analysis.box_theory.utils import atr


def htf_bias(candles: list) -> str:
    if len(candles) < 20:
        return "NEUTRAL"
    recent = candles[-20:]
    ups = sum(1 for i in range(1, len(recent)) if recent[i].close > recent[i - 1].close)
    downs = len(recent) - 1 - ups
    if ups >= downs + 6:
        return "BULLISH"
    if downs >= ups + 6:
        return "BEARISH"
    return "NEUTRAL"


def score_signal(
    *,
    box: BoxRange,
    breakout: BreakoutEvent | None,
    retest: RetestEvent | None,
    sweep: LiquiditySweep,
    fvg_confirmed: bool,
    htf: str,
    atr_expansion: bool,
    volume_confirmed: bool,
    cfg: BoxStrategyConfig,
) -> tuple[float, SignalQuality, list[str]]:
    score = 0.0
    reasons: list[str] = []
    if box.quality_score >= 50:
        score += 15
        reasons.append("Valid consolidation box")
    if breakout:
        score += 40
        reasons.append("Breakout candle close confirmed" if breakout.direction == "UP" else "Breakdown candle close confirmed")
        if breakout.body_ratio >= 0.65:
            score += 10
            reasons.append("Strong breakout body")
    if retest and retest.detected:
        score += 10
        reasons.append("Retest of box boundary")
        if retest.confirmed:
            score += 10
            reasons.append("Retest confirmation candle")
    if sweep.detected:
        score += 10
        reasons.append(f"{sweep.direction.replace('_', ' ').title()} liquidity sweep")
    if fvg_confirmed:
        score += 15
        reasons.append("FVG/iFVG confirmation")
    if cfg.htf_confirmation and htf == "BULLISH" and breakout and breakout.direction == "UP":
        score += 15
        reasons.append("HTF bullish structure")
    elif cfg.htf_confirmation and htf == "BEARISH" and breakout and breakout.direction == "DOWN":
        score += 15
        reasons.append("HTF bearish structure")
    elif cfg.htf_confirmation and htf != "NEUTRAL":
        if breakout and ((htf == "BEARISH" and breakout.direction == "UP") or (htf == "BULLISH" and breakout.direction == "DOWN")):
            score -= cfg.countertrend_penalty
            reasons.append("Counter HTF structure penalty")
    if atr_expansion:
        score += 10
        reasons.append("ATR expansion")
    if volume_confirmed:
        score += 10
        reasons.append("Volume above average")

    score = max(0.0, min(100.0, score))
    if score >= 85:
        quality = SignalQuality.VERY_HIGH
    elif score >= 70:
        quality = SignalQuality.HIGH
    elif score >= 50:
        quality = SignalQuality.MODERATE
    else:
        quality = SignalQuality.LOW
    return round(score, 1), quality, reasons


def volume_confirmed(candles: list, period: int = 20) -> bool:
    if len(candles) < period + 1:
        return False
    vols = [c.volume for c in candles[-period - 1 : -1] if c.volume > 0]
    if not vols:
        return False
    avg = sum(vols) / len(vols)
    return candles[-1].volume > avg * 1.1


def atr_expansion(candles: list, period: int = 14) -> bool:
    if len(candles) < period * 2:
        return False
    a_now = atr(candles[-period:], period)
    a_prev = atr(candles[-period * 2 : -period], period)
    return a_now > a_prev * 1.05
