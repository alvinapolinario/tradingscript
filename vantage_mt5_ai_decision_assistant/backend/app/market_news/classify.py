"""Rule-based event/news classification for macro impact."""
from __future__ import annotations

from dataclasses import dataclass

from app.market_news.types import EconomicEvent, MacroBiasDirection, NewsCategory, NormalizedNewsItem


HIGHER_IS_BULLISH: set[NewsCategory] = {
    NewsCategory.CPI_INFLATION,
    NewsCategory.EMPLOYMENT,
    NewsCategory.GDP,
    NewsCategory.PMI,
    NewsCategory.RETAIL_SALES,
    NewsCategory.INTEREST_RATE,
    NewsCategory.TRADE_BALANCE,
}

HAWKISH_TERMS = ("HAWK", "HIKE", "TIGHTEN", "HOLD RATES", "HIGHER FOR LONGER")
DOVISH_TERMS = ("DOVE", "CUT", "EASE", "LOWER RATES", "PAUSE", "PATIENCE")


@dataclass(frozen=True)
class ClassifiedImpact:
    direction: MacroBiasDirection
    confidence: float
    horizon_weight: float
    driver: str
    higher_is_bullish: bool | None = None


def category_higher_is_bullish(category: NewsCategory) -> bool | None:
    if category in HIGHER_IS_BULLISH:
        return True
    if category in {NewsCategory.GEOPOLITICAL, NewsCategory.OTHER, NewsCategory.MARKET_COMMENTARY}:
        return None
    return None


def classify_event(event: EconomicEvent) -> ClassifiedImpact:
    """Map calendar row category/importance to a directional prior."""
    higher = category_higher_is_bullish(event.category)
    imp_boost = {
        "LOW": 35.0,
        "MEDIUM": 50.0,
        "HIGH": 68.0,
        "CRITICAL": 78.0,
    }.get(event.importance.value, 50.0)
    if higher is True:
        return ClassifiedImpact(
            direction=MacroBiasDirection.NEUTRAL,
            confidence=imp_boost,
            horizon_weight=1.0,
            driver=f"Upcoming {event.category.value.replace('_', ' ').title()} ({event.event})",
            higher_is_bullish=True,
        )
    if event.category == NewsCategory.CENTRAL_BANK:
        return ClassifiedImpact(
            direction=MacroBiasDirection.NEUTRAL,
            confidence=imp_boost,
            horizon_weight=1.2,
            driver=f"Central bank event ({event.event})",
            higher_is_bullish=None,
        )
    return ClassifiedImpact(
        direction=MacroBiasDirection.NEUTRAL,
        confidence=max(30.0, imp_boost - 10.0),
        horizon_weight=0.8,
        driver=event.event,
        higher_is_bullish=higher,
    )


def classify_news_item(item: NormalizedNewsItem) -> ClassifiedImpact:
    text = f"{item.headline} {item.summary}".upper()
    direction = MacroBiasDirection.NEUTRAL
    confidence = 55.0
    driver = item.headline[:120]

    if any(term in text for term in HAWKISH_TERMS):
        direction = MacroBiasDirection.BULLISH
        confidence = 72.0
        driver = f"Hawkish headline: {item.headline[:80]}"
    elif any(term in text for term in DOVISH_TERMS):
        direction = MacroBiasDirection.BEARISH
        confidence = 72.0
        driver = f"Dovish headline: {item.headline[:80]}"
    elif item.category == NewsCategory.CENTRAL_BANK:
        confidence = 65.0
        driver = f"Central bank headline: {item.headline[:80]}"

    return ClassifiedImpact(
        direction=direction,
        confidence=confidence,
        horizon_weight=1.0,
        driver=driver,
        higher_is_bullish=category_higher_is_bullish(item.category),
    )
