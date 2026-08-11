"""High-impact economic event risk windows."""
from __future__ import annotations

from datetime import datetime, timezone

from app.market_news.types import EconomicEvent, EventRiskStatus, NewsImportance, parse_utc

_HIGH_IMPORTANCE = {NewsImportance.HIGH, NewsImportance.CRITICAL}


def _importance_rank(value: NewsImportance) -> int:
    order = {
        NewsImportance.LOW: 1,
        NewsImportance.MEDIUM: 2,
        NewsImportance.HIGH: 3,
        NewsImportance.CRITICAL: 4,
    }
    return order.get(value, 2)


def build_event_risk(
    events: list[EconomicEvent],
    *,
    now: datetime | None = None,
    before_minutes: int = 30,
    after_minutes: int = 15,
    currencies: list[str] | None = None,
) -> EventRiskStatus:
    now = now or datetime.now(timezone.utc)
    allowed = {c.upper() for c in currencies} if currencies else None

    best_minutes: int | None = None
    next_event: dict | None = None
    blocked = False

    for event in events:
        if event.importance not in _HIGH_IMPORTANCE:
            continue
        if allowed and event.currency not in allowed:
            continue
        dt = parse_utc(event.scheduled_at)
        if dt is None:
            continue

        delta_sec = (dt - now).total_seconds()
        delta_min = int(delta_sec / 60)

        if delta_sec >= 0 and delta_min <= before_minutes:
            blocked = True
        if delta_sec < 0 and (-delta_min) <= after_minutes:
            blocked = True

        if delta_sec >= 0 and (best_minutes is None or delta_min < best_minutes):
            best_minutes = delta_min
            next_event = {
                "event": event.event,
                "currency": event.currency,
                "importance": event.importance.value,
                "scheduled_at": event.scheduled_at,
            }

    message = ""
    if blocked and next_event:
        message = f"High-impact window active — {next_event['event']} ({next_event['currency']})"
    elif next_event and best_minutes is not None:
        message = f"Next high-impact: {next_event['event']} in {best_minutes}m"
    elif not events:
        message = "No calendar data ingested yet"

    return EventRiskStatus(
        blocked=blocked,
        minutes_to_next_high_impact=best_minutes,
        next_event=next_event,
        high_impact_before_minutes=before_minutes,
        high_impact_after_minutes=after_minutes,
        message=message,
    )
