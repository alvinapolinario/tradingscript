"""Market news normalized types and provider contracts — Step 2."""
from datetime import datetime, timezone

import pytest

from app.market_news.providers.base import BaseNewsProvider, NewsProvider
from app.market_news.types import (
    EconomicEventStatus,
    MacroBiasDirection,
    NewsCategory,
    NewsImportance,
    NewsSource,
    NewsTimeHorizon,
    PairMacroBias,
    economic_event_from_dict,
    event_dedupe_key,
    news_item_from_dict,
    normalize_importance,
)
from app.schemas import MarketNewsEconomicEventIn, Mt5CalendarIngestRequest, NormalizedNewsItemIn


def test_economic_event_from_mt5_payload():
    ev = economic_event_from_dict(
        {
            "source": "MT5_CALENDAR",
            "event_id": "12345",
            "currency": "USD",
            "country": "US",
            "event": "Consumer Price Index",
            "importance": "HIGH",
            "scheduled_at": "2026-08-10T12:30:00Z",
            "previous": 2.9,
            "forecast": 2.8,
            "actual": 2.6,
            "status": "RELEASED",
        }
    )
    assert ev.currency == "USD"
    assert ev.event == "Consumer Price Index"
    assert ev.importance == NewsImportance.HIGH
    assert ev.status == EconomicEventStatus.RELEASED
    assert ev.surprise == pytest.approx(-0.2)
    assert ev.content_hash


def test_economic_event_scheduled_without_actual():
    ev = economic_event_from_dict(
        {
            "currency": "JPY",
            "event": "BOJ Policy Rate",
            "scheduled_at": "2026-08-11T03:00:00+00:00",
            "importance": "CRITICAL",
        }
    )
    assert ev.status == EconomicEventStatus.SCHEDULED
    assert ev.actual is None
    assert ev.surprise is None


def test_news_item_dedupe_stable():
    payload = {
        "source": "RSS",
        "external_id": "abc-1",
        "headline": "Rate spread outlook favors JPY against USD",
        "published_at": "2026-08-10T08:00:00Z",
        "currencies": ["USD", "JPY"],
        "symbols": ["USDJPY"],
        "category": "CENTRAL_BANK",
    }
    a = news_item_from_dict(payload)
    b = news_item_from_dict(payload)
    assert a.content_hash == b.content_hash
    assert a.currencies == ["USD", "JPY"]
    assert a.category == NewsCategory.CENTRAL_BANK


def test_event_dedupe_key_uses_schedule():
    k1 = event_dedupe_key(NewsSource.MT5_CALENDAR, "999", "2026-08-10T12:30:00Z")
    k2 = event_dedupe_key(NewsSource.MT5_CALENDAR, "999", "2026-08-10T13:30:00Z")
    assert k1 != k2


def test_normalize_importance_aliases():
    assert normalize_importance("moderate") == NewsImportance.MEDIUM
    assert normalize_importance("bogus", default=NewsImportance.LOW) == NewsImportance.LOW


def test_pydantic_mt5_calendar_request():
    req = Mt5CalendarIngestRequest(
        broker="VantageInternational-Live",
        events=[
            MarketNewsEconomicEventIn(
                currency="USD",
                event="Nonfarm Payrolls",
                scheduled_at="2026-08-10T12:30:00Z",
                importance="CRITICAL",
            )
        ],
    )
    assert req.source == "MT5_CALENDAR"
    assert len(req.events) == 1
    assert req.events[0].currency == "USD"


def test_pydantic_news_item_requires_headline():
    item = NormalizedNewsItemIn(
        headline="Gold rises on softer dollar",
        published_at="2026-08-10T10:00:00Z",
        currencies=["USD"],
        symbols=["XAUUSD"],
    )
    domain = news_item_from_dict(item.model_dump())
    assert domain.symbols == ["XAUUSD"]


class _StubProvider(BaseNewsProvider):
    name = "stub"
    source = NewsSource.MANUAL

    def fetch_latest(self, *, limit: int = 50):
        return [
            news_item_from_dict(
                {
                    "source": "MANUAL",
                    "headline": "Test headline",
                    "published_at": "2026-08-10T09:00:00Z",
                }
            )
        ][:limit]

    def fetch_calendar(self, *, from_utc, to_utc, currencies=None):
        return [
            economic_event_from_dict(
                {
                    "currency": "EUR",
                    "event": "ECB Press Conference",
                    "scheduled_at": from_utc.isoformat(),
                }
            )
        ]


def test_provider_protocol_and_fetch_all():
    provider = _StubProvider()
    assert isinstance(provider, NewsProvider)
    result = provider.fetch_all(
        limit=5,
        from_utc=datetime(2026, 8, 10, tzinfo=timezone.utc),
        to_utc=datetime(2026, 8, 11, tzinfo=timezone.utc),
        currencies=["EUR"],
    )
    assert result.provider == "stub"
    assert len(result.news) == 1
    assert len(result.events) == 1
    assert result.errors == []


def test_pair_macro_bias_to_dict():
    bias = PairMacroBias(
        symbol="USDJPY",
        direction=MacroBiasDirection.BEARISH,
        confidence=78.0,
        horizon=NewsTimeHorizon.MEDIUM_TERM,
        horizons={
            "immediate": MacroBiasDirection.BULLISH,
            "medium_term": MacroBiasDirection.BEARISH,
        },
    )
    d = bias.to_dict()
    assert d["symbol"] == "USDJPY"
    assert d["horizons"]["immediate"] == "BULLISH"
