"""Event risk window tests."""
from datetime import datetime, timedelta, timezone

from app.market_news.risk_window import build_event_risk
from app.market_news.types import EconomicEvent, NewsImportance, NewsSource


def _event(minutes_ahead: int, currency: str = "USD") -> EconomicEvent:
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    scheduled = now + timedelta(minutes=minutes_ahead)
    return EconomicEvent(
        source=NewsSource.MT5_CALENDAR,
        event_id=f"evt-{minutes_ahead}",
        currency=currency,
        event="US CPI",
        scheduled_at=scheduled.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        importance=NewsImportance.HIGH,
    )


def test_risk_blocked_before_event():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    risk = build_event_risk([_event(20)], now=now, before_minutes=30, after_minutes=15)
    assert risk.blocked is True
    assert risk.minutes_to_next_high_impact == 20


def test_risk_not_blocked_far_event():
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    risk = build_event_risk([_event(120)], now=now, before_minutes=30, after_minutes=15)
    assert risk.blocked is False
    assert risk.minutes_to_next_high_impact == 120
