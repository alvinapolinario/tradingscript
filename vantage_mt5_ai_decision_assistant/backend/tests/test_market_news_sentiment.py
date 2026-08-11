"""Currency sentiment aggregation tests."""
from datetime import datetime, timezone

from app.market_news.sentiment import build_currency_sentiment
from app.market_news.types import EconomicEvent, MacroBiasDirection, NewsCategory, NewsImportance, NewsSource, NormalizedNewsItem


def _event(**kwargs) -> EconomicEvent:
    base = {
        "source": NewsSource.MT5_CALENDAR,
        "event_id": "nfp",
        "currency": "USD",
        "event": "Nonfarm Payrolls",
        "scheduled_at": "2026-08-10T12:30:00Z",
        "category": NewsCategory.EMPLOYMENT,
        "importance": NewsImportance.HIGH,
        "forecast": 175.0,
        "actual": 190.0,
        "status": "RELEASED",
    }
    base.update(kwargs)
    return EconomicEvent(**base)


def test_sentiment_bullish_on_beat():
    now = datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc)
    sent = build_currency_sentiment("USD", events=[_event()], news=[], now=now)
    assert sent.direction in {MacroBiasDirection.BULLISH, MacroBiasDirection.STRONGLY_BULLISH, MacroBiasDirection.MILD_BULLISH}
    assert sent.confidence >= 50


def test_sentiment_from_hawkish_headline():
    now = datetime(2026, 8, 10, 13, 0, tzinfo=timezone.utc)
    news = [
        NormalizedNewsItem(
            source=NewsSource.MANUAL,
            headline="Fed signals higher for longer hawkish stance",
            published_at="2026-08-10T12:00:00Z",
            currencies=["USD"],
        )
    ]
    sent = build_currency_sentiment("USD", events=[], news=news, now=now)
    assert sent.direction == MacroBiasDirection.BULLISH


def test_news_matches_eur_from_headline():
    from app.market_news.sentiment import _news_matches_currency

    item = NormalizedNewsItem(
        source=NewsSource.MANUAL,
        headline="ECB Lagarde hints at rate cut in September",
        published_at="2026-08-10T12:00:00Z",
    )
    assert _news_matches_currency(item, "EUR") is True
    assert _news_matches_currency(item, "JPY") is False


def test_news_matches_jpy_from_headline():
    from app.market_news.sentiment import _news_matches_currency

    item = NormalizedNewsItem(
        source=NewsSource.MANUAL,
        headline="BOJ Ueda keeps ultra-loose policy unchanged",
        published_at="2026-08-10T12:00:00Z",
    )
    assert _news_matches_currency(item, "JPY") is True
