"""Macro Discord notification tests (Step 12)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.macro_discord_notify import (
    _dedupe_send,
    maybe_alert_released_events,
    maybe_macro_alert,
    reset_state_for_tests,
)
from app.market_news.types import economic_event_from_dict


def _sample_release(**overrides):
    base = {
        "external_event_id": "cpi-us-discord",
        "currency": "USD",
        "event": "Core CPI m/m",
        "category": "CPI_INFLATION",
        "importance": "HIGH",
        "scheduled_at": "2026-08-12T12:30:00Z",
        "previous": 0.2,
        "forecast": 0.2,
        "actual": 0.35,
        "status": "RELEASED",
    }
    base.update(overrides)
    return economic_event_from_dict(base)


def test_macro_duplicate_discord_prevention(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.macro_discord_notify.macro_discord_configured", lambda _st=None: True)
    monkeypatch.setattr("app.macro_discord_notify._send_embed", lambda **kwargs: (True, "sent"))
    sid = "cpi-us-discord:2026-08-12T12:30:00+00:00:RELEASED"
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is True
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is False


def test_release_alert_skips_when_not_configured(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.macro_discord_notify.macro_discord_configured", lambda _st=None: False)
    sent = {"n": 0}

    def _send(**kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.macro_discord_notify._dedupe_send", _send)
    maybe_alert_released_events([_sample_release()])
    assert sent["n"] == 0


def test_release_alert_sends_for_high_impact(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.macro_discord_notify.macro_discord_configured", lambda _st=None: True)
    sent = {"n": 0, "signal_id": ""}

    def _send(signal_id, **kwargs):
        sent["n"] += 1
        sent["signal_id"] = signal_id
        return True

    monkeypatch.setattr("app.macro_discord_notify._dedupe_send", _send)
    maybe_alert_released_events([_sample_release()])
    assert sent["n"] == 1
    assert sent["signal_id"].startswith("cpi-us-discord:")
    assert sent["signal_id"].endswith(":RELEASED")


def test_release_alert_skips_medium_importance(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.macro_discord_notify.macro_discord_configured", lambda _st=None: True)
    sent = {"n": 0}
    monkeypatch.setattr("app.macro_discord_notify._dedupe_send", lambda *a, **k: sent.__setitem__("n", sent["n"] + 1) or True)
    maybe_alert_released_events([_sample_release(importance="MEDIUM")])
    assert sent["n"] == 0


def test_approaching_alert_on_heartbeat(monkeypatch, tmp_path):
    reset_state_for_tests()
    from app.config import get_settings
    from app.market_news import store as news_store
    from app.market_news.providers.registry import get_registry

    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_registry.cache_clear()
    get_settings.cache_clear()

    soon_dt = datetime.now(timezone.utc) + timedelta(minutes=14)
    soon = soon_dt.replace(microsecond=0).isoformat()
    news_store.upsert_economic_event(
        economic_event_from_dict(
            {
                "external_event_id": "nfp-soon",
                "currency": "USD",
                "event": "Nonfarm Payrolls",
                "importance": "HIGH",
                "scheduled_at": soon,
                "forecast": 180.0,
            }
        )
    )

    monkeypatch.setattr("app.macro_discord_notify.macro_discord_configured", lambda _st=None: True)
    sent = {"n": 0}
    monkeypatch.setattr("app.macro_discord_notify._dedupe_send", lambda *a, **k: sent.__setitem__("n", sent["n"] + 1) or True)

    maybe_macro_alert({"symbol": "XAUUSD"})
    assert sent["n"] >= 1


def test_alignment_alert_requires_technical_confirmation(monkeypatch, tmp_path):
    reset_state_for_tests()
    from app.config import get_settings
    from app.market_news import store as news_store
    from app.market_news.providers.registry import get_registry

    db = tmp_path / "market_news.db"
    monkeypatch.setattr(news_store, "_DB_PATH", db)
    monkeypatch.setattr(news_store, "_DATA_DIR", tmp_path)
    news_store.init_db()
    get_registry.cache_clear()
    get_settings.cache_clear()

    news_store.upsert_economic_event(
        economic_event_from_dict(
            {
                "external_event_id": "cpi-align",
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

    monkeypatch.setattr("app.macro_discord_notify.macro_discord_configured", lambda _st=None: True)
    sent = {"n": 0}
    monkeypatch.setattr("app.macro_discord_notify._dedupe_send", lambda *a, **k: sent.__setitem__("n", sent["n"] + 1) or True)

    payload = {
        "symbol": "XAUUSD",
        "ict": {
            "valid": True,
            "analysis_active": True,
            "setup_state": "MSS_CONFIRMED",
            "status": "MSS_CONFIRMED",
            "decision": "SELL",
            "htf_bias": {"direction": "BEARISH"},
        },
    }
    maybe_macro_alert(payload)
    assert sent["n"] >= 1
