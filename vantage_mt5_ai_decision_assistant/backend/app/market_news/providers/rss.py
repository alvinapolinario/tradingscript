"""RSS news provider — configurable feeds, no API key required."""
from __future__ import annotations

from datetime import datetime
from typing import Sequence

import httpx

from app.config import Settings, get_settings
from app.market_news.classify import classify_news_item
from app.market_news.providers.base import BaseNewsProvider
from app.market_news.providers.rss_parser import parse_feed_xml
from app.market_news.store import list_news_items, news_from_row
from app.market_news.types import EconomicEvent, NewsCategory, NewsImportance, NewsSource, NormalizedNewsItem, news_item_from_dict

_CATEGORY_HINTS: tuple[tuple[str, NewsCategory], ...] = (
    ("CPI", NewsCategory.CPI_INFLATION),
    ("INFLATION", NewsCategory.CPI_INFLATION),
    ("NFP", NewsCategory.EMPLOYMENT),
    ("NONFARM", NewsCategory.EMPLOYMENT),
    ("UNEMPLOYMENT", NewsCategory.EMPLOYMENT),
    ("GDP", NewsCategory.GDP),
    ("PMI", NewsCategory.PMI),
    ("FOMC", NewsCategory.CENTRAL_BANK),
    ("CENTRAL BANK", NewsCategory.CENTRAL_BANK),
    ("INTEREST RATE", NewsCategory.INTEREST_RATE),
    ("GEOPOLIT", NewsCategory.GEOPOLITICAL),
    ("OIL", NewsCategory.ENERGY),
    ("GOLD", NewsCategory.COMMODITY),
    ("XAU", NewsCategory.COMMODITY),
)

_CCY_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("USD", (" USD", " U.S.", " FED", " FOMC", "DOLLAR", "UNITED STATES")),
    ("EUR", (" EUR", " EURO", " ECB", "EUROZONE")),
    ("GBP", (" GBP", " BOE", " STERLING", " BRITAIN", " UK ")),
    ("JPY", (" JPY", " BOJ", " YEN", " JAPAN")),
    ("AUD", (" AUD", " RBA", " AUSTRALIA")),
    ("NZD", (" NZD", " RBNZ", " NEW ZEALAND")),
    ("CAD", (" CAD", " BOC", " CANADA")),
    ("CHF", (" CHF", " SNB", " SWISS")),
)


def parse_rss_feed_urls(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for part in raw.split(","):
        url = part.strip()
        if url.startswith("http://") or url.startswith("https://"):
            out.append(url)
    return out


def guess_category(headline: str, summary: str = "") -> NewsCategory:
    text = f"{headline} {summary}".upper()
    for needle, category in _CATEGORY_HINTS:
        if needle in text:
            return category
    return NewsCategory.MARKET_COMMENTARY


def infer_currencies(headline: str, summary: str = "") -> list[str]:
    text = f" {headline} {summary} ".upper()
    found: list[str] = []
    for ccy, hints in _CCY_HINTS:
        if any(hint in text for hint in hints):
            found.append(ccy)
    return found


def _importance_from_text(text: str) -> NewsImportance:
    upper = text.upper()
    if any(k in upper for k in ("BREAKING", "FOMC", "NFP", "CPI", "RATE DECISION")):
        return NewsImportance.HIGH
    if any(k in upper for k in ("FED", "ECB", "BOE", "INFLATION", "EMPLOYMENT")):
        return NewsImportance.MEDIUM
    return NewsImportance.LOW


class RssNewsProvider(BaseNewsProvider):
    """Fetch headlines from configured RSS/Atom feeds and read persisted rows."""

    name = "rss"
    source = NewsSource.RSS

    def __init__(self, feed_urls: list[str] | None = None, settings: Settings | None = None) -> None:
        st = settings or get_settings()
        self._feed_urls = feed_urls if feed_urls is not None else parse_rss_feed_urls(st.market_news_rss_feeds)
        self._timeout = float(st.market_news_external_fetch_timeout_sec)

    def pull_remote(self, *, limit: int = 50) -> tuple[list[NormalizedNewsItem], list[str]]:
        """HTTP fetch from all configured feeds (used by POST /fetch)."""
        items: list[NormalizedNewsItem] = []
        errors: list[str] = []
        per_feed = max(1, limit // max(1, len(self._feed_urls)))

        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            for feed_url in self._feed_urls:
                try:
                    resp = client.get(feed_url, headers={"User-Agent": "VantageMacroNews/1.0"})
                    if resp.status_code >= 400:
                        errors.append(f"{feed_url}: HTTP {resp.status_code}")
                        continue
                    rows = parse_feed_xml(resp.content, feed_url=feed_url)
                except Exception as exc:
                    errors.append(f"{feed_url}: {exc}")
                    continue

                for row in rows[:per_feed]:
                    item = self._normalize_row(row)
                    classified = classify_news_item(item)
                    if classified.confidence >= 70:
                        item.importance = NewsImportance.HIGH
                    items.append(item)

        items.sort(key=lambda x: x.published_at, reverse=True)
        return items[:limit], errors

    def _normalize_row(self, row: dict) -> NormalizedNewsItem:
        headline = str(row.get("headline") or "")
        summary = str(row.get("summary") or "")
        return news_item_from_dict(
            {
                "source": NewsSource.RSS.value,
                "external_id": row.get("external_id") or row.get("raw_url") or headline,
                "headline": headline,
                "summary": summary,
                "published_at": row.get("published_at"),
                "raw_url": row.get("raw_url") or "",
                "currencies": infer_currencies(headline, summary),
                "category": guess_category(headline, summary).value,
                "importance": _importance_from_text(f"{headline} {summary}").value,
            },
            default_source=NewsSource.RSS,
        )

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
