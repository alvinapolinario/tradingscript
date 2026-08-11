"""Time decay for macro relevance weighting."""
from __future__ import annotations

from datetime import datetime, timezone

from app.market_news.types import EconomicEventStatus, NewsCategory, NewsImportance, parse_utc


def _hours_between(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 3600.0


def event_relevance_weight(
    *,
    scheduled_at: str,
    status: str,
    importance: NewsImportance,
    category: NewsCategory,
    now: datetime | None = None,
) -> float:
    """0–1 weight; upcoming events peak near release, released events decay."""
    now = now or datetime.now(timezone.utc)
    dt = parse_utc(scheduled_at)
    if dt is None:
        return 0.35

    imp_scale = {
        NewsImportance.LOW: 0.6,
        NewsImportance.MEDIUM: 0.85,
        NewsImportance.HIGH: 1.0,
        NewsImportance.CRITICAL: 1.15,
    }.get(importance, 0.85)
    cat_scale = 1.1 if category in {NewsCategory.CENTRAL_BANK, NewsCategory.INTEREST_RATE, NewsCategory.CPI_INFLATION} else 1.0

    hours = (dt - now).total_seconds() / 3600.0
    released = str(status).upper() in {
        EconomicEventStatus.RELEASED.value,
        EconomicEventStatus.REVISED.value,
    }

    if not released and hours >= 0:
        if hours <= 2:
            time_scale = 1.0
        elif hours <= 24:
            time_scale = 0.85
        elif hours <= 72:
            time_scale = 0.65
        elif hours <= 168:
            time_scale = 0.45
        else:
            time_scale = 0.25
    elif released or hours < 0:
        age = _hours_between(now, dt)
        if age <= 1:
            time_scale = 1.0
        elif age <= 6:
            time_scale = 0.75
        elif age <= 24:
            time_scale = 0.5
        elif age <= 72:
            time_scale = 0.3
        else:
            time_scale = 0.15
    else:
        time_scale = 0.4

    return round(min(1.2, imp_scale * cat_scale * time_scale), 3)
