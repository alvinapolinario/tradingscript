"""Market news provider abstraction — Step 5."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.market_news import store as news_store
from app.market_news.providers.manual import ManualNewsProvider
from app.market_news.providers.mt5_calendar import Mt5CalendarProvider
from app.market_news.providers.registry import ProviderRegistry, get_registry
from app.market_news.types import NewsSource


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_registry.cache_clear()
    return db


def _seed_calendar_event(**overrides):
    payload = {
        "source": "MT5_CALENDAR",
        "external_event_id": "evt-1",
        "currency": "USD",
        "country": "US",
        "event": "Nonfarm Payrolls",
        "importance": "HIGH",
        "scheduled_at": "2026-08-10T12:30:00Z",
        "forecast": 175.0,
        "status": "SCHEDULED",
    }
    payload.update(overrides)
    from app.market_news.types import economic_event_from_dict

    news_store.upsert_economic_event(economic_event_from_dict(payload))


def _seed_manual_news(**overrides):
    payload = {
        "source": "MANUAL",
        "external_id": "manual-1",
        "headline": "Fed signals patience on cuts",
        "published_at": "2026-08-10T14:00:00Z",
        "currencies": ["USD"],
        "importance": "HIGH",
    }
    payload.update(overrides)
    from app.market_news.types import news_item_from_dict

    news_store.upsert_news_item(news_item_from_dict(payload, default_source=NewsSource.MANUAL))


def test_registry_lists_default_providers():
    registry = get_registry()
    names = registry.names()
    assert "mt5_calendar" in names
    assert "manual" in names


def test_mt5_calendar_provider_reads_db(tmp_market_news_db):
    _seed_calendar_event()
    provider = Mt5CalendarProvider()
    events = provider.fetch_calendar()
    assert len(events) == 1
    assert events[0].event == "Nonfarm Payrolls"
    assert events[0].source == NewsSource.MT5_CALENDAR


def test_mt5_calendar_provider_filters_window(tmp_market_news_db):
    _seed_calendar_event(scheduled_at="2026-08-10T12:30:00Z")
    _seed_calendar_event(external_event_id="evt-2", scheduled_at="2026-01-01T12:30:00Z", event="Old CPI")
    provider = Mt5CalendarProvider()
    start = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)
    events = provider.fetch_calendar(from_utc=start, to_utc=end)
    assert len(events) == 1
    assert events[0].event == "Nonfarm Payrolls"


def test_manual_provider_reads_headlines(tmp_market_news_db):
    _seed_manual_news()
    provider = ManualNewsProvider()
    items = provider.fetch_latest(limit=10)
    assert len(items) == 1
    assert items[0].headline.startswith("Fed signals")
    assert items[0].source == NewsSource.MANUAL


def test_registry_merges_latest(tmp_market_news_db):
    _seed_manual_news()
    registry = ProviderRegistry()
    registry.register(ManualNewsProvider())
    items, results = registry.fetch_latest(limit=10, providers=["manual"])
    assert len(items) == 1
    assert len(results) == 1
    assert len(results[0].news) == 1


def test_registry_calendar_unbounded(tmp_market_news_db):
    _seed_calendar_event(scheduled_at="2026-01-01T12:30:00Z", event="Old CPI")
    registry = ProviderRegistry()
    registry.register(Mt5CalendarProvider())
    events, _ = registry.fetch_calendar(unbounded=True, limit=10)
    assert len(events) == 1
    assert events[0].event == "Old CPI"
