"""Registry of market news providers — calendar + textual sources."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Sequence

from app.config import get_settings
from app.market_news.providers.base import NewsProvider, ProviderFetchResult
from app.market_news.providers.manual import ManualNewsProvider
from app.market_news.providers.mt5_calendar import Mt5CalendarProvider
from app.market_news.types import EconomicEvent, NormalizedNewsItem


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, NewsProvider] = {}

    def register(self, provider: NewsProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> NewsProvider | None:
        return self._providers.get(name)

    def names(self) -> list[str]:
        return sorted(self._providers.keys())

    def describe(self) -> list[dict]:
        out: list[dict] = []
        for name in self.names():
            p = self._providers[name]
            out.append(
                {
                    "name": name,
                    "source": p.source.value,
                    "calendar": hasattr(p, "fetch_calendar"),
                    "headlines": hasattr(p, "fetch_latest"),
                }
            )
        return out

    def fetch_latest(
        self,
        *,
        limit: int = 50,
        providers: Sequence[str] | None = None,
    ) -> tuple[list[NormalizedNewsItem], list[ProviderFetchResult]]:
        selected = self._select(providers)
        merged: list[NormalizedNewsItem] = []
        seen: set[str] = set()
        results: list[ProviderFetchResult] = []
        per_provider = max(1, limit // max(1, len(selected)))

        for provider in selected:
            try:
                items = provider.fetch_latest(limit=per_provider)
            except Exception as exc:
                results.append(
                    ProviderFetchResult(
                        provider=provider.name,
                        source=provider.source,
                        errors=[str(exc)],
                    )
                )
                continue
            results.append(
                ProviderFetchResult(
                    provider=provider.name,
                    source=provider.source,
                    news=items,
                )
            )
            for item in items:
                key = item.content_hash or item.headline
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)

        merged.sort(key=lambda x: x.published_at, reverse=True)
        return merged[:limit], results

    def fetch_calendar(
        self,
        *,
        from_utc: datetime | None = None,
        to_utc: datetime | None = None,
        currencies: Sequence[str] | None = None,
        limit: int = 500,
        providers: Sequence[str] | None = None,
        unbounded: bool = False,
    ) -> tuple[list[EconomicEvent], list[ProviderFetchResult]]:
        now = datetime.now(timezone.utc)
        if unbounded:
            start = from_utc
            end = to_utc
        else:
            start = from_utc if from_utc is not None else (now - timedelta(hours=6))
            end = to_utc if to_utc is not None else (now + timedelta(days=7))
        selected = self._select(providers, calendar_only=True)

        merged: list[EconomicEvent] = []
        seen: set[str] = set()
        results: list[ProviderFetchResult] = []

        for provider in selected:
            batch = provider.fetch_all(
                limit=0,
                from_utc=start,
                to_utc=end,
                currencies=currencies,
                include_calendar=True,
            )
            results.append(batch)
            for event in batch.events:
                key = event.event_id or event.content_hash
                if key in seen:
                    continue
                seen.add(key)
                merged.append(event)

        merged.sort(key=lambda x: x.scheduled_at, reverse=True)
        return merged[:limit], results

    def _select(
        self,
        names: Sequence[str] | None = None,
        *,
        calendar_only: bool = False,
    ) -> list[NewsProvider]:
        if names:
            out: list[NewsProvider] = []
            for name in names:
                provider = self.get(name)
                if provider:
                    out.append(provider)
            return out

        if calendar_only:
            return [p for p in self._providers.values() if p.name == "mt5_calendar"]
        return list(self._providers.values())


@lru_cache
def get_registry() -> ProviderRegistry:
    st = get_settings()
    registry = ProviderRegistry()
    registry.register(Mt5CalendarProvider())
    registry.register(ManualNewsProvider())
    if st.market_news_rss_enabled and (st.market_news_rss_feeds or "").strip():
        from app.market_news.providers.rss import RssNewsProvider

        registry.register(RssNewsProvider(settings=st))
    if st.market_news_api_enabled and (st.newsapi_key or "").strip():
        from app.market_news.providers.newsapi import NewsApiProvider

        registry.register(NewsApiProvider(settings=st))
    return registry
