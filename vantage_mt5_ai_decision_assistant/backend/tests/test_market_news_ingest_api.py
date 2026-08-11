"""Manual news ingest API — POST /api/v1/market-news/ingest."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.market_news import store as news_store
from app.market_news.providers.registry import get_registry

client = TestClient(app)


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_registry.cache_clear()
    get_settings.cache_clear()
    return db


def _auth_headers():
    token = get_settings().local_api_token
    return {"Authorization": f"Bearer {token}"}


def test_news_ingest_requires_bearer():
    r = client.post("/api/v1/market-news/ingest", json={"items": []})
    assert r.status_code == 401


def test_news_ingest_and_latest(tmp_market_news_db):
    payload = {
        "items": [
            {
                "headline": "ECB holds rates steady",
                "published_at": "2026-08-11T12:00:00Z",
                "currencies": ["EUR"],
                "importance": "HIGH",
                "category": "CENTRAL_BANK",
            }
        ]
    }
    r = client.post("/api/v1/market-news/ingest", json=payload, headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["inserted"] == 1
    assert body["received"] == 1

    latest = client.get("/api/v1/market-news/latest?source=manual")
    assert latest.status_code == 200
    items = latest.json()["items"]
    assert len(items) == 1
    assert items[0]["headline"] == "ECB holds rates steady"
    assert items[0]["source"] == "MANUAL"


def test_news_ingest_dedupes(tmp_market_news_db):
    payload = {
        "items": [
            {
                "external_id": "dup-1",
                "headline": "Same headline",
                "published_at": "2026-08-11T12:00:00Z",
            }
        ]
    }
    h = _auth_headers()
    r1 = client.post("/api/v1/market-news/ingest", json=payload, headers=h)
    r2 = client.post("/api/v1/market-news/ingest", json=payload, headers=h)
    assert r1.json()["inserted"] == 1
    assert r2.json()["unchanged"] == 1


def test_providers_endpoint(tmp_market_news_db):
    r = client.get("/api/v1/market-news/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    names = {p["name"] for p in body["providers"]}
    assert "mt5_calendar" in names
    assert "manual" in names
