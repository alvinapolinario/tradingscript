"""Central bank context — seed + event overlay tests."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.market_news import store as news_store
from app.market_news.central_bank import (
    build_central_bank_context,
    load_seed_banks,
    merge_central_bank_context,
    refresh_central_bank_overlays,
)
from app.market_news.types import (
    CentralBankContext,
    EconomicEvent,
    NewsCategory,
    NewsImportance,
    NewsSource,
    NormalizedNewsItem,
)


@pytest.fixture()
def tmp_market_news_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    load_seed_banks.cache_clear()
    return db


def test_load_seed_includes_major_currencies():
    seeds = load_seed_banks()
    assert "USD" in seeds
    assert seeds["USD"].central_bank == "Federal Reserve"
    assert "JPY" in seeds
    assert seeds["JPY"].policy_bias in {"MILD_HAWKISH", "NEUTRAL", "HAWKISH", "MILD_DOVISH", "DOVISH"}


def test_merge_shifts_bias_on_hawkish_headline():
    seed = load_seed_banks()["USD"]
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    news = [
        NormalizedNewsItem(
            source=NewsSource.MANUAL,
            headline="Fed officials lean hawkish on rates",
            published_at="2026-08-10T11:00:00Z",
            currencies=["USD"],
        )
    ]
    ctx = merge_central_bank_context(seed, events=[], news=news, now=now)
    assert _bias_rank(ctx.policy_bias) >= _bias_rank(seed.policy_bias)


def test_merge_sets_next_meeting_from_upcoming_event():
    seed = load_seed_banks()["JPY"]
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    meeting = now + timedelta(days=1)
    events = [
        EconomicEvent(
            source=NewsSource.MT5_CALENDAR,
            event_id="boj1",
            currency="JPY",
            event="BOJ Policy Rate Decision",
            scheduled_at=meeting.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            category=NewsCategory.INTEREST_RATE,
            importance=NewsImportance.HIGH,
        )
    ]
    ctx = merge_central_bank_context(seed, events=events, news=[], now=now)
    assert ctx.next_meeting_at is not None


def test_merge_updates_policy_rate_from_release():
    seed = load_seed_banks()["USD"]
    now = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
    events = [
        EconomicEvent(
            source=NewsSource.MT5_CALENDAR,
            event_id="fed-rate",
            currency="USD",
            event="FOMC Interest Rate Decision",
            scheduled_at="2026-08-10T18:00:00Z",
            category=NewsCategory.INTEREST_RATE,
            importance=NewsImportance.CRITICAL,
            actual=5.50,
            forecast=5.25,
            status="RELEASED",
        )
    ]
    ctx = merge_central_bank_context(seed, events=events, news=[], now=now)
    assert ctx.policy_rate == pytest.approx(5.50)


def test_refresh_overlays_persists_to_store(tmp_market_news_db):
    events = [
        EconomicEvent(
            source=NewsSource.MT5_CALENDAR,
            event_id="fed-rate",
            currency="USD",
            event="FOMC Interest Rate Decision",
            scheduled_at="2026-08-10T18:00:00Z",
            category=NewsCategory.INTEREST_RATE,
            importance=NewsImportance.CRITICAL,
            actual=5.50,
            forecast=5.25,
            status="RELEASED",
        )
    ]
    overlays = refresh_central_bank_overlays(events)
    assert len(overlays) == 1
    news_store.upsert_central_bank_context(overlays[0], source="EVENT")
    stored = news_store.get_central_bank_overlay("USD")
    assert stored is not None
    assert stored.policy_rate == pytest.approx(5.50)


def test_build_context_returns_none_for_unknown_currency():
    ctx = build_central_bank_context("XYZ", events=[], news=[])
    assert ctx is None


def _bias_rank(bias: str) -> int:
    order = ["DOVISH", "MILD_DOVISH", "NEUTRAL", "MILD_HAWKISH", "HAWKISH"]
    return order.index(bias) if bias in order else 2
