"""Actual vs forecast surprise engine — no fabricated economic values."""
from __future__ import annotations

from dataclasses import dataclass

from app.market_news.classify import category_higher_is_bullish
from app.market_news.types import EconomicEvent, MacroBiasDirection, NewsCategory


@dataclass(frozen=True)
class SurpriseInterpretation:
    surprise: float
    pct_surprise: float | None
    direction: MacroBiasDirection
    confidence: float
    label: str
    driver: str


def compute_surprise(event: EconomicEvent) -> float | None:
    if event.actual is None or event.forecast is None:
        return None
    return event.actual - event.forecast


def compute_pct_surprise(event: EconomicEvent, surprise: float) -> float | None:
    if event.forecast in (None, 0):
        return None
    return (surprise / abs(event.forecast)) * 100.0


def _magnitude_confidence(surprise: float, pct: float | None) -> float:
    base = min(92.0, 55.0 + abs(surprise) * 4.0)
    if pct is not None:
        base = min(92.0, base + min(20.0, abs(pct) * 0.5))
    return round(base, 1)


def _label_for_surprise(surprise: float, threshold: float = 0.05) -> str:
    if abs(surprise) <= threshold:
        return "INLINE"
    return "BEAT" if surprise > 0 else "MISS"


def interpret_surprise(event: EconomicEvent) -> SurpriseInterpretation | None:
    """Directional read when actual and forecast are both present."""
    surprise = compute_surprise(event)
    if surprise is None:
        return None

    pct = compute_pct_surprise(event, surprise)
    label = _label_for_surprise(surprise)
    higher_bullish = category_higher_is_bullish(event.category)

    if label == "INLINE" or higher_bullish is None:
        direction = MacroBiasDirection.NEUTRAL
        confidence = 45.0
        driver = f"{event.event}: inline vs forecast"
    elif higher_bullish:
        direction = MacroBiasDirection.BULLISH if surprise > 0 else MacroBiasDirection.BEARISH
        confidence = _magnitude_confidence(surprise, pct)
        driver = f"{event.event}: {label.lower()} forecast ({surprise:+.3g})"
    else:
        direction = MacroBiasDirection.NEUTRAL
        confidence = 50.0
        driver = f"{event.event}: surprise {surprise:+.3g}"

    if event.category == NewsCategory.INTEREST_RATE and surprise > 0:
        direction = MacroBiasDirection.BULLISH
        confidence = max(confidence, 70.0)

    return SurpriseInterpretation(
        surprise=surprise,
        pct_surprise=round(pct, 2) if pct is not None else None,
        direction=direction,
        confidence=confidence,
        label=label,
        driver=driver,
    )
