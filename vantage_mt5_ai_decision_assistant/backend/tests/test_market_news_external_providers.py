"""External news providers — RSS parser, NewsAPI, fetch orchestration (Step 13)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.market_news import store as news_store
from app.market_news.external_fetch import fetch_and_persist_external_news
from app.market_news.providers.newsapi import NewsApiProvider
from app.market_news.providers.registry import get_registry
from app.market_news.providers.rss import RssNewsProvider, parse_rss_feed_urls
from app.market_news.providers.rss_parser import parse_feed_xml

client = TestClient(app)

SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Fed signals patience on USD rate cuts</title>
      <link>https://example.com/fed-usd</link>
      <guid>fed-usd-1</guid>
      <pubDate>Mon, 10 Aug 2026 14:00:00 GMT</pubDate>
      <description>US CPI outlook remains firm.</description>
    </item>
  </channel>
</rss>"""


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_registry.cache_clear()
    get_settings.cache_clear()
    return db


def test_parse_rss_feed_xml():
    rows = parse_feed_xml(SAMPLE_RSS, feed_url="https://example.com/feed")
    assert len(rows) == 1
    assert "Fed signals" in rows[0]["headline"]
    assert rows[0]["external_id"] == "fed-usd-1"


def test_parse_rss_feed_urls():
    urls = parse_rss_feed_urls(" https://a.com/rss , not-a-url , https://b.com/atom ")
    assert urls == ["https://a.com/rss", "https://b.com/atom"]


def test_rss_pull_remote(monkeypatch):
    class FakeResp:
        status_code = 200
        content = SAMPLE_RSS

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr("app.market_news.providers.rss.httpx.Client", FakeClient)
    provider = RssNewsProvider(feed_urls=["https://example.com/feed"])
    items, errors = provider.pull_remote(limit=5)
    assert not errors
    assert len(items) == 1
    assert items[0].source.value == "RSS"
    assert "USD" in items[0].currencies


def test_newsapi_pull_remote(monkeypatch):
    class FakeResp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "ok",
                "articles": [
                    {
                        "title": "Gold rises as USD weakens",
                        "description": "XAUUSD gains on FOMC outlook",
                        "url": "https://example.com/gold",
                        "publishedAt": "2026-08-10T14:00:00Z",
                    }
                ],
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None, headers=None):
            return FakeResp()

    monkeypatch.setattr("app.market_news.providers.newsapi.httpx.Client", FakeClient)
    st = Settings(newsapi_key="test-key", market_news_api_enabled=True)
    provider = NewsApiProvider(settings=st)
    items, errors = provider.pull_remote(limit=5)
    assert not errors
    assert len(items) == 1
    assert "Gold" in items[0].headline


def test_fetch_and_persist_external_news(tmp_market_news_db, monkeypatch):
    class FakeResp:
        status_code = 200
        content = SAMPLE_RSS

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None, params=None):
            return FakeResp()

    monkeypatch.setattr("app.market_news.providers.rss.httpx.Client", FakeClient)
    st = Settings(
        market_news_enabled=True,
        market_news_rss_enabled=True,
        market_news_rss_feeds="https://example.com/feed",
    )
    result = fetch_and_persist_external_news(st, limit=10)
    assert result["ok"] is True
    assert result["received"] == 1
    assert result["inserted"] == 1

    monkeypatch.setenv("MARKET_NEWS_RSS_ENABLED", "true")
    monkeypatch.setenv("MARKET_NEWS_RSS_FEEDS", "https://example.com/feed")
    get_settings.cache_clear()
    get_registry.cache_clear()

    latest = client.get("/api/v1/market-news/latest?source=rss")
    assert latest.status_code == 200
    assert latest.json()["count"] == 1


def test_registry_registers_external_providers_when_enabled(monkeypatch):
    get_settings.cache_clear()
    get_registry.cache_clear()
    monkeypatch.setenv("MARKET_NEWS_RSS_ENABLED", "true")
    monkeypatch.setenv("MARKET_NEWS_RSS_FEEDS", "https://example.com/feed")
    monkeypatch.setenv("MARKET_NEWS_API_ENABLED", "true")
    monkeypatch.setenv("NEWSAPI_KEY", "test-key")
    get_settings.cache_clear()
    get_registry.cache_clear()
    names = get_registry().names()
    assert "rss" in names
    assert "newsapi" in names


def test_fetch_api_requires_bearer(tmp_market_news_db):
    r = client.post("/api/v1/market-news/fetch")
    assert r.status_code == 401


def test_fetch_api_with_bearer(tmp_market_news_db, monkeypatch):
    token = get_settings().local_api_token

    class FakeResp:
        status_code = 200
        content = SAMPLE_RSS

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None, params=None):
            return FakeResp()

    monkeypatch.setattr("app.market_news.providers.rss.httpx.Client", FakeClient)
    monkeypatch.setenv("MARKET_NEWS_RSS_ENABLED", "true")
    monkeypatch.setenv("MARKET_NEWS_RSS_FEEDS", "https://example.com/feed")
    get_settings.cache_clear()

    r = client.post(
        "/api/v1/market-news/fetch",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["received"] >= 1
