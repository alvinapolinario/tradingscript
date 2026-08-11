"""MT5 calendar provider — reads persisted bridge data from SQLite."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.market_news.providers.base import BaseNewsProvider
from app.market_news.store import event_from_row, list_economic_events
from app.market_news.types import EconomicEvent, NewsSource, NormalizedNewsItem


class Mt5CalendarProvider(BaseNewsProvider):
    """Economic calendar rows ingested via POST /api/v1/market-news/mt5-calendar."""

    name = "mt5_calendar"
    source = NewsSource.MT5_CALENDAR

    def fetch_latest(self, *, limit: int = 50) -> list[NormalizedNewsItem]:
        return []

    def fetch_calendar(
        self,
        *,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
        currencies: Sequence[str] | None = None,
    ) -> list[EconomicEvent]:
        from_iso = from_utc.astimezone(timezone.utc).isoformat() if from_utc else None
        to_iso = to_utc.astimezone(timezone.utc).isoformat() if to_utc else None
        currency_filter = currencies[0].upper() if currencies and len(currencies) == 1 else None
        rows = list_economic_events(
            limit=500,
            currency=currency_filter,
            from_utc=from_iso,
            to_utc=to_iso,
            source=self.source.value,
        )
        events = [event_from_row(row) for row in rows]
        if currencies and len(currencies) > 1:
            allowed = {c.upper() for c in currencies}
            events = [ev for ev in events if ev.currency in allowed]
        return events
