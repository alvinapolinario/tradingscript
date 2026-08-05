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
    mock_settings.return_value = _settings(discord_trades_only=False, telegram_alert_entry=True)
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


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_trades_only_skips_entry_alert(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings(discord_trades_only=True)
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    process_heartbeat(
        {
            "symbol": "XAUUSD",
            "new_entry_decision": "BUY_ALLOWED",
            "trend": "BULLISH",
            "bid": 2650.0,
        }
    )
    assert not mock_client_cls.return_value.__enter__.return_value.post.called


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_trades_only_master_setup(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings(discord_trades_only=True, discord_cooldown_sec=0)
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    process_heartbeat(
        {
            "symbol": "XAUUSD",
            "connected": True,
            "new_entry_decision": "BUY_ALLOWED",
            "risk_status": "LOW",
            "swing_strategy": {
                "valid": True,
                "signal": "STRONG SWING BUY",
                "confidence": 91.0,
                "entry_quality": "Excellent",
            },
        }
    )
    assert mock_client_cls.return_value.__enter__.return_value.post.called


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_amd_ifvg_buy_alert(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings(discord_trades_only=True, discord_cooldown_sec=0)
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    process_heartbeat(
        {
            "symbol": "XAUUSD",
            "amd_ifvg": {
                "valid": True,
                "gold_symbol_valid": True,
                "decision": "BUY",
                "confidence": 87.0,
                "setup_state": "ENTRY_ZONE_ACTIVE",
                "amd_phase": "DISTRIBUTION",
                "eval_bar_m5": 1710000000,
                "entry": {"preferred_entry": 2650.5, "entry_low": 2649.0, "entry_high": 2652.0},
                "risk": {"stop_loss": 2645.0},
            },
        }
    )
    assert mock_client_cls.return_value.__enter__.return_value.post.called
    body = mock_client_cls.return_value.__enter__.return_value.post.call_args.kwargs.get("json") or {}
    embed = (body.get("embeds") or [{}])[0]
    assert "AMD + iFVG" in embed.get("description", "")


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_amd_ifvg_skips_low_confidence(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings(discord_trades_only=True)
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    process_heartbeat(
        {
            "symbol": "XAUUSD",
            "amd_ifvg": {
                "valid": True,
                "decision": "WAIT",
                "confidence": 55.0,
                "setup_state": "WAITING_FOR_RETRACE",
            },
        }
    )
    assert not mock_client_cls.return_value.__enter__.return_value.post.called


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_amd_ifvg_entry_zone_wait_trades_only(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings(discord_trades_only=True, discord_cooldown_sec=0)
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    process_heartbeat(
        {
            "symbol": "XAUUSD",
            "amd_ifvg": {
                "valid": True,
                "gold_symbol_valid": True,
                "decision": "WAIT",
                "confidence": 78.0,
                "setup_state": "ENTRY_ZONE_ACTIVE",
                "amd_phase": "DISTRIBUTION",
                "eval_bar_m5": 1710000001,
            },
        }
    )
    assert mock_client_cls.return_value.__enter__.return_value.post.called


@patch("app.discord_notify.get_settings")
@patch("app.discord_notify.httpx.Client")
def test_monitor_discord_test(mock_client_cls, mock_settings):
    mock_settings.return_value = _settings()
    mock_client_cls.return_value.__enter__.return_value.post.side_effect = _mock_post_ok
    r = client.post("/api/v1/monitor/discord/test")
    assert r.status_code == 200
    assert r.json()["ok"] is True
