"""Pull external news providers (RSS / licensed API) and persist to SQLite."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.market_news.providers.newsapi import NewsApiProvider
from app.market_news.providers.rss import RssNewsProvider
from app.market_news.store import UpsertStats, upsert_news_items
from app.market_news.types import NormalizedNewsItem


def fetch_and_persist_external_news(
    settings: Settings | None = None,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Fetch enabled remote providers and upsert headlines into market_news.db."""
    st = settings or get_settings()
    if not st.market_news_enabled:
        return {"advisory_only": True, "enabled": False, "ok": False}

    merged: list[NormalizedNewsItem] = []
    provider_reports: list[dict[str, Any]] = []
    errors: list[str] = []

    if st.market_news_rss_enabled:
        rss = RssNewsProvider(settings=st)
        items, rss_errors = rss.pull_remote(limit=limit)
        merged.extend(items)
        errors.extend(rss_errors)
        provider_reports.append(
            {
                "provider": rss.name,
                "fetched": len(items),
                "errors": rss_errors,
                "feeds": len(rss._feed_urls),
            }
        )

    if st.market_news_api_enabled and (st.newsapi_key or "").strip():
        api = NewsApiProvider(settings=st)
        items, api_errors = api.pull_remote(limit=limit)
        merged.extend(items)
        errors.extend(api_errors)
        provider_reports.append(
            {
                "provider": api.name,
                "fetched": len(items),
                "errors": api_errors,
            }
        )

    if not provider_reports:
        return {
            "advisory_only": True,
            "enabled": True,
            "ok": False,
            "message": "No external providers enabled — set MARKET_NEWS_RSS_ENABLED or MARKET_NEWS_API_ENABLED",
            "providers": [],
            "errors": errors,
        }

    stats: UpsertStats = upsert_news_items(merged)
    return {
        "advisory_only": True,
        "enabled": True,
        "ok": stats.errors == 0 or stats.inserted + stats.updated + stats.unchanged > 0,
        "received": len(merged),
        "providers": provider_reports,
        "errors": errors,
        **stats.to_dict(),
    }
