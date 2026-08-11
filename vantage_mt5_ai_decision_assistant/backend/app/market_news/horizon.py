"""Multi-horizon macro bias assignment."""
from __future__ import annotations

from datetime import datetime, timezone

from app.market_news.sentiment import direction_to_score, score_to_direction
from app.market_news.surprise import interpret_surprise
from app.market_news.types import EconomicEvent, MacroBiasDirection, NormalizedNewsItem, parse_utc

HORIZON_KEYS = ("immediate", "intraday", "swing", "medium_term")


def _minutes_to_event(scheduled_at: str, now: datetime) -> float | None:
    dt = parse_utc(scheduled_at)
    if dt is None:
        return None
    return (dt - now).total_seconds() / 60.0


def horizon_bucket_for_event(scheduled_at: str, now: datetime) -> str:
    minutes = _minutes_to_event(scheduled_at, now)
    if minutes is None:
        return "medium_term"
    if minutes <= 240:
        return "immediate"
    if minutes <= 1440:
        return "intraday"
    if minutes <= 10080:
        return "swing"
    return "medium_term"


def _event_direction(event: EconomicEvent) -> MacroBiasDirection:
    surprise = interpret_surprise(event)
    if surprise:
        return surprise.direction
    return MacroBiasDirection.NEUTRAL


def build_horizon_map(
    *,
    base_ccy: str,
    quote_ccy: str,
    events: list[EconomicEvent],
    news: list[NormalizedNewsItem],
    now: datetime | None = None,
) -> dict[str, MacroBiasDirection]:
    now = now or datetime.now(timezone.utc)
    buckets: dict[str, list[float]] = {k: [] for k in HORIZON_KEYS}

    for event in events:
        if event.currency not in {base_ccy, quote_ccy}:
            continue
        bucket = horizon_bucket_for_event(event.scheduled_at, now)
        sign = 1.0 if event.currency == base_ccy else -1.0
        buckets[bucket].append(direction_to_score(_event_direction(event)) * sign)

    for item in news:
        for ccy in item.currencies:
            if ccy not in {base_ccy, quote_ccy}:
                continue
            dt = parse_utc(item.published_at)
            if dt is None:
                bucket = "intraday"
            else:
                age_min = max(0.0, (now - dt).total_seconds() / 60.0)
                if age_min <= 240:
                    bucket = "immediate"
                elif age_min <= 1440:
                    bucket = "intraday"
                elif age_min <= 10080:
                    bucket = "swing"
                else:
                    bucket = "medium_term"
            sign = 1.0 if ccy == base_ccy else -1.0
            from app.market_news.classify import classify_news_item

            classified = classify_news_item(item)
            buckets[bucket].append(direction_to_score(classified.direction) * sign)

    out: dict[str, MacroBiasDirection] = {}
    for key in HORIZON_KEYS:
        scores = buckets[key]
        if not scores:
            out[key] = MacroBiasDirection.NEUTRAL
        else:
            avg = sum(scores) / len(scores)
            out[key], _ = score_to_direction(avg)
    return out
