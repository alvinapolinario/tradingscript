"""Market news SQLite store — upsert and listing."""
from pathlib import Path

import pytest

from app.market_news import store as news_store
from app.market_news.types import NewsSource, economic_event_from_dict


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    return db


def _sample_event(**overrides):
    payload = {
        "source": "MT5_CALENDAR",
        "external_event_id": "evt-100",
        "currency": "USD",
        "country": "US",
        "event": "Consumer Price Index",
        "importance": "HIGH",
        "scheduled_at": "2026-08-10T12:30:00Z",
        "previous": 2.9,
        "forecast": 2.8,
        "actual": None,
        "status": "SCHEDULED",
    }
    payload.update(overrides)
    return economic_event_from_dict(payload, default_source=NewsSource.MT5_CALENDAR)


def test_upsert_inserts_event(tmp_market_news_db):
    ev = _sample_event()
    assert news_store.upsert_economic_event(ev, broker="Vantage") == "inserted"
    rows = news_store.list_economic_events(currency="USD")
    assert len(rows) == 1
    assert rows[0]["event"] == "Consumer Price Index"
    assert rows[0]["broker"] == "Vantage"


def test_upsert_dedupes_unchanged(tmp_market_news_db):
    ev = _sample_event()
    assert news_store.upsert_economic_event(ev) == "inserted"
    assert news_store.upsert_economic_event(ev) == "unchanged"
    assert len(news_store.list_economic_events()) == 1


def test_upsert_updates_actual(tmp_market_news_db):
    ev = _sample_event()
    news_store.upsert_economic_event(ev)
    updated = _sample_event(actual=2.6, status="RELEASED")
    assert news_store.upsert_economic_event(updated) == "updated"
    row = news_store.get_economic_event(updated.event_id)
    assert row is not None
    assert row["actual"] == pytest.approx(2.6)
    assert row["status"] == "RELEASED"


def test_upsert_batch_stats(tmp_market_news_db):
    stats = news_store.upsert_economic_events(
        [
            _sample_event(external_event_id="a"),
            _sample_event(external_event_id="b", currency="EUR", event="ECB Rate"),
        ]
    )
    assert stats.inserted == 2
    assert stats.errors == 0


def test_list_filters_currency(tmp_market_news_db):
    news_store.upsert_economic_events(
        [
            _sample_event(external_event_id="usd"),
            _sample_event(external_event_id="eur", currency="EUR", event="German CPI"),
        ]
    )
    usd = news_store.list_economic_events(currency="USD")
    assert len(usd) == 1
    assert usd[0]["currency"] == "USD"
