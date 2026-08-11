"""MQL5 VantageMacroBridge payload shape — integration smoke test."""
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


def test_mql5_bridge_fixture_payload(tmp_market_news_db):
    """Payload mirrors VantageMacroBridge.mqh BuildPayloadJson()."""
    payload = {
        "source": "MT5_CALENDAR",
        "server_time_utc": "2026-08-11T00:00:00Z",
        "terminal": "MetaTrader 5",
        "broker": "VantageInternational-Live",
        "events": [
            {
                "event_id": "840030001",
                "external_event_id": "840030001",
                "currency": "USD",
                "country": "US",
                "event": "Core CPI m/m",
                "category": "CPI_INFLATION",
                "importance": "HIGH",
                "scheduled_at": "2026-08-12T12:30:00Z",
                "previous": 0.3,
                "forecast": 0.2,
                "actual": None,
                "status": "SCHEDULED",
            },
            {
                "event_id": "392060002",
                "external_event_id": "392060002",
                "currency": "JPY",
                "country": "JP",
                "event": "BOJ Outlook Report",
                "category": "CENTRAL_BANK",
                "importance": "HIGH",
                "scheduled_at": "2026-08-11T03:00:00Z",
                "previous": None,
                "forecast": None,
                "actual": None,
                "status": "SCHEDULED",
            },
        ],
    }
    r = client.post(
        "/api/v1/market-news/mt5-calendar",
        json=payload,
        headers=_auth_headers(),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["inserted"] == 2
    assert body["received"] == 2

    listed = client.get("/api/v1/market-news/calendar?currency=USD")
    assert listed.status_code == 200
    usd = listed.json()["items"]
    assert len(usd) == 1
    assert usd[0]["category"] == "CPI_INFLATION"
    assert usd[0]["event"] == "Core CPI m/m"
