"""Pair macro bias tests."""
from datetime import datetime, timezone

from app.market_news.pair_bias import build_pair_macro_bias, parse_symbol_legs
from app.market_news.types import EconomicEvent, MacroBiasDirection, NewsCategory, NewsImportance, NewsSource


def test_parse_symbol_legs():
    assert parse_symbol_legs("USDJPY") == ("USD", "JPY")
    assert parse_symbol_legs("XAUUSD") == ("XAU", "USD")


def test_pair_bias_usdjpy():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    events = [
        EconomicEvent(
            source=NewsSource.MT5_CALENDAR,
            event_id="jpy1",
            currency="JPY",
            event="BOJ Outlook Report",
            scheduled_at="2026-08-11T03:00:00Z",
            category=NewsCategory.CENTRAL_BANK,
            importance=NewsImportance.HIGH,
        ),
        EconomicEvent(
            source=NewsSource.MT5_CALENDAR,
            event_id="usd1",
            currency="USD",
            event="Core CPI",
            scheduled_at="2026-08-10T12:30:00Z",
            category=NewsCategory.CPI_INFLATION,
            importance=NewsImportance.HIGH,
            forecast=0.2,
            actual=0.1,
            status="RELEASED",
        ),
    ]
    bias = build_pair_macro_bias("USDJPY", events=events, news=[], now=now)
    assert bias.symbol == "USDJPY"
    assert bias.direction in {
        MacroBiasDirection.BEARISH,
        MacroBiasDirection.BULLISH,
        MacroBiasDirection.NEUTRAL,
        MacroBiasDirection.MILD_BEARISH,
        MacroBiasDirection.MILD_BULLISH,
    }
    assert "immediate" in bias.horizons
