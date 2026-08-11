"""Market news ingest API — MT5 calendar POST."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.market_news import store as news_store

client = TestClient(app)


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_settings.cache_clear()
    return db


def _auth_headers():
    token = get_settings().local_api_token
    return {"Authorization": f"Bearer {token}"}


def test_mt5_calendar_requires_bearer():
    r = client.post(
        "/api/v1/market-news/mt5-calendar",
        json={"events": []},
    )
    assert r.status_code == 401


def test_mt5_calendar_ingest_and_list(tmp_market_news_db):
    payload = {
        "source": "MT5_CALENDAR",
        "server_time_utc": "2026-08-10T12:00:00Z",
        "terminal": "MetaTrader 5",
        "broker": "VantageInternational-Live",
        "events": [
            {
                "event_id": "12345",
                "currency": "USD",
                "country": "US",
                "event": "Nonfarm Payrolls",
                "importance": "CRITICAL",
                "scheduled_at": "2026-08-10T12:30:00Z",
                "previous": 180.0,
                "forecast": 175.0,
                "status": "SCHEDULED",
            }
        ],
    }
    r = client.post("/api/v1/market-news/mt5-calendar", json=payload, headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["inserted"] == 1
    assert body["received"] == 1
    assert body["broker"] == "VantageInternational-Live"

    listed = client.get("/api/v1/market-news/calendar?currency=USD")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["event"] == "Nonfarm Payrolls"


def test_mt5_calendar_dedupes_repeat_post(tmp_market_news_db):
    payload = {
        "events": [
            {
                "external_event_id": "999",
                "currency": "JPY",
                "event": "BOJ Outlook Report",
                "scheduled_at": "2026-08-11T03:00:00Z",
                "importance": "HIGH",
            }
        ],
    }
    h = _auth_headers()
    r1 = client.post("/api/v1/market-news/mt5-calendar", json=payload, headers=h)
    r2 = client.post("/api/v1/market-news/mt5-calendar", json=payload, headers=h)
    assert r1.json()["inserted"] == 1
    assert r2.json()["unchanged"] == 1
    assert len(client.get("/api/v1/market-news/calendar").json()["items"]) == 1


def test_mt5_calendar_updates_actual(tmp_market_news_db):
    base = {
        "events": [
            {
                "external_event_id": "cpi-us",
                "currency": "USD",
                "event": "CPI",
                "scheduled_at": "2026-08-10T12:30:00Z",
                "forecast": 2.8,
                "status": "SCHEDULED",
            }
        ],
    }
    h = _auth_headers()
    client.post("/api/v1/market-news/mt5-calendar", json=base, headers=h)
    released = {
        "events": [
            {
                "external_event_id": "cpi-us",
                "currency": "USD",
                "event": "CPI",
                "scheduled_at": "2026-08-10T12:30:00Z",
                "forecast": 2.8,
                "actual": 2.6,
                "status": "RELEASED",
            }
        ],
    }
    r = client.post("/api/v1/market-news/mt5-calendar", json=released, headers=h)
    assert r.json()["updated"] == 1
    item = client.get("/api/v1/market-news/calendar").json()["items"][0]
    assert item["actual"] == pytest.approx(2.6)
