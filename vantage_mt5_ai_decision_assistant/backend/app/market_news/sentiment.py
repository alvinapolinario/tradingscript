"""Currency-level macro sentiment aggregation."""
from __future__ import annotations

from datetime import datetime, timezone

from app.market_news.classify import classify_event, classify_news_item
from app.market_news.decay import event_relevance_weight
from app.market_news.surprise import interpret_surprise
from app.market_news.types import (
    CurrencySentiment,
    EconomicEvent,
    MacroBiasDirection,
    NewsTimeHorizon,
    NormalizedNewsItem,
    parse_utc,
)

_DIRECTION_SCORE = {
    MacroBiasDirection.STRONGLY_BULLISH: 2.0,
    MacroBiasDirection.BULLISH: 1.0,
    MacroBiasDirection.MILD_BULLISH: 0.5,
    MacroBiasDirection.NEUTRAL: 0.0,
    MacroBiasDirection.MILD_BEARISH: -0.5,
    MacroBiasDirection.BEARISH: -1.0,
    MacroBiasDirection.STRONGLY_BEARISH: -2.0,
}


def direction_to_score(direction: MacroBiasDirection) -> float:
    return _DIRECTION_SCORE.get(direction, 0.0)


def score_to_direction(score: float) -> tuple[MacroBiasDirection, float]:
    if score >= 1.4:
        return MacroBiasDirection.STRONGLY_BULLISH, min(92.0, 70.0 + abs(score) * 8.0)
    if score >= 0.55:
        return MacroBiasDirection.BULLISH, min(88.0, 58.0 + abs(score) * 18.0)
    if score >= 0.2:
        return MacroBiasDirection.MILD_BULLISH, min(75.0, 50.0 + abs(score) * 20.0)
    if score <= -1.4:
        return MacroBiasDirection.STRONGLY_BEARISH, min(92.0, 70.0 + abs(score) * 8.0)
    if score <= -0.55:
        return MacroBiasDirection.BEARISH, min(88.0, 58.0 + abs(score) * 18.0)
    if score <= -0.2:
        return MacroBiasDirection.MILD_BEARISH, min(75.0, 50.0 + abs(score) * 20.0)
    return MacroBiasDirection.NEUTRAL, max(35.0, 50.0 - abs(score) * 10.0)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _event_contribution(event: EconomicEvent, now: datetime) -> tuple[float, float, str]:
    weight = event_relevance_weight(
        scheduled_at=event.scheduled_at,
        status=_enum_value(event.status),
        importance=event.importance,
        category=event.category,
        now=now,
    )
    surprise = interpret_surprise(event)
    if surprise:
        score = direction_to_score(surprise.direction) * weight * (surprise.confidence / 100.0)
        return score, weight * surprise.confidence, surprise.driver

    classified = classify_event(event)
    score = direction_to_score(classified.direction) * weight * (classified.confidence / 100.0)
    return score, weight * classified.confidence, classified.driver


def _news_contribution(item: NormalizedNewsItem, now: datetime) -> tuple[float, float, str]:
    dt = parse_utc(item.published_at)
    age_h = 999.0 if dt is None else max(0.0, (now - dt).total_seconds() / 3600.0)
    weight = 0.85 if age_h <= 6 else 0.55 if age_h <= 24 else 0.3 if age_h <= 72 else 0.15
    imp_scale = {"HIGH": 1.1, "CRITICAL": 1.2}.get(item.importance.value, 1.0)
    weight *= imp_scale
    classified = classify_news_item(item)
    score = direction_to_score(classified.direction) * weight * (classified.confidence / 100.0)
    return score, weight * classified.confidence, classified.driver


def _news_matches_currency(item: NormalizedNewsItem, ccy: str) -> bool:
    if ccy in item.currencies:
        return True
    text = f" {item.headline} {item.summary} ".upper()
    if ccy == "XAU" and any(k in text for k in (" GOLD", " XAU", "PRECIOUS METAL")):
        return True
    if ccy == "EUR" and any(k in text for k in (" EUR", " EURO", " ECB", "EUROZONE")):
        return True
    if ccy == "JPY" and any(k in text for k in (" JPY", " YEN", " BOJ", "JAPAN")):
        return True
    if ccy == "USD" and any(k in text for k in (" USD", " U.S.", " FED", " FOMC", "DOLLAR")):
        return True
    return False


def build_currency_sentiment(
    currency: str,
    *,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
) -> CurrencySentiment:
    now = now or datetime.now(timezone.utc)
    ccy = currency.upper()
    total_score = 0.0
    total_weight = 0.0
    drivers: list[str] = []

    for event in events:
        if event.currency != ccy:
            continue
        score, w, driver = _event_contribution(event, now)
        total_score += score
        total_weight += w
        if w >= 25 and driver:
            drivers.append(driver)

    for item in news:
        if not _news_matches_currency(item, ccy):
            continue
        score, w, driver = _news_contribution(item, now)
        total_score += score
        total_weight += w
        if w >= 20 and driver:
            drivers.append(driver)

    if total_weight <= 0:
        return CurrencySentiment(
            currency=ccy,
            direction=MacroBiasDirection.NEUTRAL,
            confidence=35.0,
            horizon=NewsTimeHorizon.INTRADAY,
            drivers=["No recent macro inputs for this currency"],
            as_of_utc=now.isoformat(),
        )

    norm_score = total_score / max(0.01, total_weight / 100.0)
    direction, confidence = score_to_direction(norm_score)
    horizon = NewsTimeHorizon.INTRADAY if abs(norm_score) >= 0.8 else NewsTimeHorizon.SHORT_TERM

    return CurrencySentiment(
        currency=ccy,
        direction=direction,
        confidence=round(confidence, 1),
        horizon=horizon,
        drivers=drivers[:8] or [f"Aggregated macro score {norm_score:+.2f}"],
        as_of_utc=now.isoformat(),
    )
