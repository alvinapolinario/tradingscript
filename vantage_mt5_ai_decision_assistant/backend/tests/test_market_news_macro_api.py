"""Macro intelligence API — currency/symbol/status endpoints."""
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


def _seed_usd_cpi():
    from app.market_news.types import economic_event_from_dict

    news_store.upsert_economic_event(
        economic_event_from_dict(
            {
                "external_event_id": "cpi-us",
                "currency": "USD",
                "event": "Core CPI m/m",
                "category": "CPI_INFLATION",
                "importance": "HIGH",
                "scheduled_at": "2026-08-12T12:30:00Z",
                "forecast": 0.2,
                "actual": 0.35,
                "status": "RELEASED",
            }
        )
    )


def test_currency_endpoint(tmp_market_news_db):
    _seed_usd_cpi()
    r = client.get("/api/v1/market-news/currency/USD")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["currency"] == "USD"
    assert "sentiment" in body
    assert body["sentiment"]["currency"] == "USD"
    assert body["central_bank"]["central_bank"] == "Federal Reserve"
    assert body["central_bank"]["currency"] == "USD"


def test_symbol_endpoint(tmp_market_news_db):
    _seed_usd_cpi()
    r = client.get("/api/v1/market-news/symbol/USDJPY")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "USDJPY"
    assert "macro_bias" in body
    assert "horizons" in body
    assert "event_risk" in body
    assert "technical_alignment" in body
    assert "USD" in body["currency_bias"]
    assert "JPY" in body["currency_bias"]
    assert "USD" in body["central_bank"]
    assert body["central_bank"]["USD"]["central_bank"] == "Federal Reserve"
    assert "JPY" in body["central_bank"]


def test_status_endpoint(tmp_market_news_db):
    _seed_usd_cpi()
    r = client.get("/api/v1/market-news/status?symbol=XAUUSD")
    assert r.status_code == 200
    body = r.json()
    assert body["module"] == "market_news"
    assert "status_line" in body
    assert body["symbol"] == "XAUUSD"


def test_status_includes_major_fx_pairs(tmp_market_news_db):
    _seed_usd_cpi()
    r = client.get("/api/v1/market-news/status?symbol=EURUSD")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "EURUSD"
    assert "major_pairs" in body
    assert "EURUSD" in body["major_pairs"]
    assert "USDJPY" in body["major_pairs"]
    assert "XAUUSD" in body["major_pairs"]
    eur = body["major_pairs"]["EURUSD"]
    assert "macro_bias" in eur
    assert "EUR" in eur.get("currency_bias", {})
    assert "USD" in eur.get("currency_bias", {})
