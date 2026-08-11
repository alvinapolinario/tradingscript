"""Manual news provider — reads user-ingested headlines from SQLite."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

from app.market_news.providers.base import BaseNewsProvider
from app.market_news.store import list_news_items, news_from_row
from app.market_news.types import EconomicEvent, NewsSource, NormalizedNewsItem


class ManualNewsProvider(BaseNewsProvider):
    """Textual news rows ingested via POST /api/v1/market-news/ingest."""

    name = "manual"
    source = NewsSource.MANUAL

    def fetch_latest(self, *, limit: int = 50) -> list[NormalizedNewsItem]:
        rows = list_news_items(limit=limit, source=self.source.value)
        return [news_from_row(row) for row in rows]

    def fetch_calendar(
        self,
        *,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
        currencies: Sequence[str] | None = None,
    ) -> list[EconomicEvent]:
        return []
