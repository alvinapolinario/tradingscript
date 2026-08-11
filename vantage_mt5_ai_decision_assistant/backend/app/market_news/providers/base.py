"""News provider abstraction — multiple sources, one normalized output."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, Sequence, runtime_checkable

from app.market_news.types import EconomicEvent, NormalizedNewsItem, NewsSource


@dataclass
class ProviderFetchResult:
    """Batch result from a single provider call."""

    provider: str
    source: NewsSource
    news: list[NormalizedNewsItem] = field(default_factory=list)
    events: list[EconomicEvent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fetched_at_utc: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "source": self.source.value,
            "news_count": len(self.news),
            "events_count": len(self.events),
            "errors": self.errors,
            "fetched_at_utc": self.fetched_at_utc,
        }


@runtime_checkable
class NewsProvider(Protocol):
    """Adapter contract for calendar + textual news sources."""

    name: str
    source: NewsSource

    def fetch_latest(self, *, limit: int = 50) -> list[NormalizedNewsItem]:
        """Return recent normalized news headlines."""
        ...

    def fetch_calendar(
        self,
        *,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
        currencies: Sequence[str] | None = None,
    ) -> list[EconomicEvent]:
        """Return economic calendar events in the requested window."""
        ...


class BaseNewsProvider(ABC):
    """Optional base class with shared metadata."""

    name: str = "base"
    source: NewsSource = NewsSource.NEWS_PROVIDER

    @abstractmethod
    def fetch_latest(self, *, limit: int = 50) -> list[NormalizedNewsItem]:
        raise NotImplementedError

    @abstractmethod
    def fetch_calendar(
        self,
        *,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
        currencies: Sequence[str] | None = None,
    ) -> list[EconomicEvent]:
        raise NotImplementedError

    def fetch_all(
        self,
        *,
        limit: int = 50,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
        currencies: Sequence[str] | None = None,
        include_calendar: bool = True,
    ) -> ProviderFetchResult:
        errors: list[str] = []
        news: list[NormalizedNewsItem] = []
        events: list[EconomicEvent] = []
        if limit > 0:
            try:
                news = self.fetch_latest(limit=limit)
            except Exception as exc:
                errors.append(f"{self.name} fetch_latest failed: {exc}")
        if include_calendar:
            try:
                events = self.fetch_calendar(from_utc=from_utc, to_utc=to_utc, currencies=currencies)
            except Exception as exc:
                errors.append(f"{self.name} fetch_calendar failed: {exc}")
        return ProviderFetchResult(
            provider=self.name,
            source=self.source,
            news=news,
            events=events,
            errors=errors,
            fetched_at_utc=datetime.now(timezone.utc).isoformat(),
        )
