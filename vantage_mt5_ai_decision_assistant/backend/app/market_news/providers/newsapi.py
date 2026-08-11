"""Licensed NewsAPI.org adapter — requires API key."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

import httpx

from app.config import Settings, get_settings
from app.market_news.providers.base import BaseNewsProvider
from app.market_news.providers.rss import guess_category, infer_currencies, _importance_from_text
from app.market_news.store import list_news_items, news_from_row
from app.market_news.types import EconomicEvent, NewsSource, NormalizedNewsItem, news_item_from_dict


class NewsApiProvider(BaseNewsProvider):
    """Fetch business/macro headlines via NewsAPI.org (NEWSAPI_KEY)."""

    name = "newsapi"
    source = NewsSource.NEWS_PROVIDER

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._timeout = float(self._settings.market_news_external_fetch_timeout_sec)

    def pull_remote(self, *, limit: int = 50) -> tuple[list[NormalizedNewsItem], list[str]]:
        key = (self._settings.newsapi_key or "").strip()
        if not key:
            return [], ["NEWSAPI_KEY missing"]

        query = (self._settings.newsapi_query or "forex OR gold OR federal reserve").strip()
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(max(1, limit), 100),
        }
        headers = {"X-Api-Key": key}

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get("https://newsapi.org/v2/everything", params=params, headers=headers)
            if resp.status_code >= 400:
                return [], [f"NewsAPI HTTP {resp.status_code}: {resp.text[:200]}"]
            data = resp.json()
        except Exception as exc:
            return [], [str(exc)]

        if str(data.get("status") or "").lower() != "ok":
            return [], [str(data.get("message") or "NewsAPI error")]

        items: list[NormalizedNewsItem] = []
        for article in data.get("articles") or []:
            if not isinstance(article, dict):
                continue
            headline = str(article.get("title") or "").strip()
            if not headline or headline == "[Removed]":
                continue
            summary = str(article.get("description") or "")
            published = str(article.get("publishedAt") or "")
            url = str(article.get("url") or "")
            ext_id = url or headline
            items.append(
                news_item_from_dict(
                    {
                        "source": NewsSource.NEWS_PROVIDER.value,
                        "external_id": ext_id,
                        "headline": headline,
                        "summary": summary,
                        "published_at": published,
                        "raw_url": url,
                        "currencies": infer_currencies(headline, summary),
                        "category": guess_category(headline, summary).value,
                        "importance": _importance_from_text(f"{headline} {summary}").value,
                    },
                    default_source=NewsSource.NEWS_PROVIDER,
                )
            )

        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit], []

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
