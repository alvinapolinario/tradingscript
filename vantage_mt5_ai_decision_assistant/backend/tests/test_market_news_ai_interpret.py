"""AI news interpretation — rule-based + cache (Step 11)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.market_news import store as news_store
from app.market_news.ai_interpret import (
    analysis_input_hash,
    build_analysis_facts,
    interpret_macro,
    rule_based_analysis,
    validate_no_hallucinated_numbers,
)
from app.market_news.types import economic_event_from_dict

client = TestClient(app)


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_settings.cache_clear()
    return db


def _seed_cpi():
    news_store.upsert_economic_event(
        economic_event_from_dict(
            {
                "external_event_id": "cpi-us-ai",
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


def test_rule_based_interpret(tmp_market_news_db):
    _seed_cpi()
    settings = get_settings()
    facts = build_analysis_facts(symbol="XAUUSD", settings=settings)
    record = rule_based_analysis(facts)
    assert record.headline
    assert record.analysis_hash == analysis_input_hash(facts)
    assert "XAUUSD" in record.symbols


def test_interpret_macro_caches(tmp_market_news_db):
    _seed_cpi()
    settings = get_settings()
    first = interpret_macro(symbol="XAUUSD", settings=settings)
    assert first["status"] == "ok"
    assert first["mode"] == "rule_based"
    assert first.get("cached") is False

    second = interpret_macro(symbol="XAUUSD", settings=settings)
    assert second.get("cached") is True


def test_analyze_api_endpoint(tmp_market_news_db):
    _seed_cpi()
    r = client.post("/api/v1/market-news/analyze", json={"symbol": "XAUUSD"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["symbol"] == "XAUUSD"
    assert "drivers" in body


def test_hallucination_guard_flags_unknown_numbers():
    facts = {"events": [{"forecast": 0.2, "actual": 0.35}]}
    parsed = {"headline": "Hot CPI", "drivers": ["Actual 0.35 beat forecast 0.2", "Mystery 9.99 print"]}
    issues = validate_no_hallucinated_numbers(parsed, facts)
    assert any("9.99" in issue for issue in issues)


def test_status_includes_desk_sections(tmp_market_news_db):
    _seed_cpi()
    r = client.get("/api/v1/market-news/status?symbol=XAUUSD")
    assert r.status_code == 200
    body = r.json()
    assert "news_feed" in body
    assert "calendar_table" in body
    assert "major_currency_bias" in body
    assert "USD" in body["major_currency_bias"]
