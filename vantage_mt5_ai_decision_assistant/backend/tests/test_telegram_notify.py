"""Telegram notification tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.telegram_notify import (
    process_heartbeat,
    reset_state_for_tests,
    send_test_message,
    telegram_configured,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_tg_state():
    reset_state_for_tests()
    yield
    reset_state_for_tests()


def _settings(**overrides) -> Settings:
    base = get_settings().model_dump()
    base.update(
        {
            "telegram_enabled": True,
            "telegram_bot_token": "123456:ABC-DEF",
            "telegram_chat_id": "999001",
            "telegram_cooldown_sec": 0,
        }
    )
    base.update(overrides)
    return Settings(**base)


def _mock_post_ok(*_args, **_kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"ok": True}
    resp.text = '{"ok":true}'
    return resp


@patch("app.telegram_notify.get_settings")
@patch("app.telegram_notify.httpx.Client")
def test_send_test_message(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings()
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    ok, detail = send_test_message()
    assert ok is True
    assert detail == "sent"


@patch("app.telegram_notify.get_settings")
@patch("app.telegram_notify.httpx.Client")
def test_process_heartbeat_critical_risk(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings()
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    process_heartbeat(
        {
            "symbol": "XAUUSD",
            "risk_status": "CRITICAL",
            "exceeds_max_position_risk": True,
            "equity_risk_pct": 12.5,
            "action": "CRITICAL_RISK",
        }
    )
    assert mock_client_cls.return_value.__enter__.return_value.post.called


@patch("app.telegram_notify.get_settings")
@patch("app.telegram_notify.httpx.Client")
def test_process_heartbeat_entry_dedupe(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings()
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    payload = {
        "symbol": "XAUUSD",
        "new_entry_decision": "BUY_ALLOWED",
        "trend": "BULLISH",
        "bid": 2650.0,
    }
    process_heartbeat(payload)
    process_heartbeat(payload)
    assert mock_client_cls.return_value.__enter__.return_value.post.call_count == 1


@patch("app.telegram_notify.get_settings")
def test_telegram_not_configured(mock_settings):
    mock_settings.return_value = _settings(telegram_enabled=False)
    assert telegram_configured() is False


def test_health_shows_telegram_block():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "telegram" in body
    assert "enabled" in body["telegram"]


def test_telegram_test_requires_auth():
    r = client.post("/api/v1/telegram/test")
    assert r.status_code == 401
