"""Surprise engine unit tests."""
from app.market_news.surprise import compute_surprise, interpret_surprise
from app.market_news.types import EconomicEvent, MacroBiasDirection, NewsCategory, NewsImportance, NewsSource


def _event(**kwargs) -> EconomicEvent:
    base = {
        "source": NewsSource.MT5_CALENDAR,
        "event_id": "1",
        "currency": "USD",
        "event": "Core CPI m/m",
        "scheduled_at": "2026-08-10T12:30:00Z",
        "category": NewsCategory.CPI_INFLATION,
        "importance": NewsImportance.HIGH,
        "forecast": 0.2,
        "actual": 0.4,
        "status": "RELEASED",
    }
    base.update(kwargs)
    return EconomicEvent(**base)


def test_compute_surprise():
    assert compute_surprise(_event()) == 0.2


def test_interpret_surprise_beat_is_bullish_for_cpi():
    result = interpret_surprise(_event())
    assert result is not None
    assert result.label == "BEAT"
    assert result.direction == MacroBiasDirection.BULLISH
    assert result.surprise == 0.2


def test_interpret_surprise_inline():
    result = interpret_surprise(_event(actual=0.2))
    assert result is not None
    assert result.label == "INLINE"
    assert result.direction == MacroBiasDirection.NEUTRAL


def test_interpret_surprise_missing_values():
    assert interpret_surprise(_event(actual=None, forecast=0.2)) is None
