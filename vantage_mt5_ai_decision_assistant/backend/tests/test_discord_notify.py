"""Discord webhook notification tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.discord_notify import (
    discord_configured,
    process_heartbeat,
    reset_state_for_tests,
    send_test_message,
)
from app.main import app

client = TestClient(app)

WEBHOOK = "https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(autouse=True)
def _reset_dc_state():
    reset_state_for_tests()
    yield
    reset_state_for_tests()


def _settings(**overrides) -> Settings:
    base = get_settings().model_dump()
    base.update(
        {
            "discord_enabled": True,
            "discord_webhook_url": WEBHOOK,
            "discord_cooldown_sec": 0,
        }
    )
    base.update(overrides)
    return Settings(**base)


def _mock_post_ok(*_args, **_kwargs):
    resp = MagicMock()
    resp.status_code = 204
    resp.text = ""
    return resp


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_send_test_message(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings()
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    ok, detail = send_test_message()
    assert ok is True
    assert detail == "sent"


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
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


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
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


@patch("app.discord_notify.get_settings")
def test_discord_accepts_discordapp_url(mock_settings):
    mock_settings.return_value = _settings(
        discord_webhook_url="https://discordapp.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz"
    )
    assert discord_configured() is True


@patch("app.discord_notify.get_settings")
def test_discord_not_configured(mock_settings):
    mock_settings.return_value = _settings(discord_enabled=False)
    assert discord_configured() is False


def test_health_shows_discord_block():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "discord" in body
    assert "enabled" in body["discord"]


def test_discord_test_requires_auth():
    r = client.post("/api/v1/discord/test")
    assert r.status_code == 401
