"""ICT Discord notification tests."""
from app.ict_discord_notify import (
    _dedupe_send,
    maybe_ict_alert,
    reset_state_for_tests,
)


def _sample_blob(**overrides):
    base = {
        "module": "ict",
        "valid": True,
        "analysis_active": True,
        "gold_symbol_valid": True,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "setup_state": "MSS_CONFIRMED",
        "status": "MSS_CONFIRMED",
        "decision": "WAIT",
        "confidence": 82,
        "confidence_score": 82,
        "signal_quality": "HIGH",
        "setup_id": "ICT-XAUUSD-M15-1700038700-S",
        "state_changed": True,
        "htf_bias": {"direction": "BEARISH", "confidence": 78},
        "liquidity": {"sweep_detected": True, "type": "BUY_SIDE", "level": 4011.0},
        "structure": {"mss": "BEARISH", "displacement_score": 72},
        "fvg": {"low": 4005.0, "high": 4010.0},
        "entry": {"zone_low": 4006.0, "zone_high": 4009.0},
        "stop_loss": {"price": 4015.0},
        "targets": [{"name": "TP1", "price": 3995.0}],
        "risk_reward": 2.4,
        "reasons": ["Bearish MSS after buy-side sweep"],
    }
    base.update(overrides)
    return base


def test_duplicate_discord_prevention(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    monkeypatch.setattr("app.ict_discord_notify._send_embed", lambda **kwargs: (True, "sent"))
    sid = "ICT-XAUUSD-M15-1700038700-S|MSS_CONFIRMED"
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is True
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is False


def test_maybe_ict_alert_skips_when_not_configured(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: False)
    sent = {"n": 0}

    def _send(**kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert({"ict": _sample_blob()})
    assert sent["n"] == 0


def test_maybe_ict_alert_skips_without_state_change(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    sent = {"n": 0}

    def _send(**kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert({"ict": _sample_blob(state_changed=False)})
    assert sent["n"] == 0


def test_maybe_ict_alert_skips_low_confidence(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    sent = {"n": 0}

    def _send(**kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert({"ict": _sample_blob(confidence=50, confidence_score=50)})
    assert sent["n"] == 0


def test_maybe_ict_alert_sends_on_allowed_state(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    sent = {"n": 0, "signal_id": ""}

    def _send(signal_id, **kwargs):
        sent["n"] += 1
        sent["signal_id"] = signal_id
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert({"ict": _sample_blob()})
    assert sent["n"] == 1
    assert sent["signal_id"] == "ICT-XAUUSD-M15-1700038700-S|MSS_CONFIRMED"


def test_maybe_ict_alert_skips_unlisted_state(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    sent = {"n": 0}

    def _send(**kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert({"ict": _sample_blob(setup_state="WAITING_FOR_RETRACE", status="WAITING_FOR_RETRACE")})
    assert sent["n"] == 0


def test_invalidated_alert_bypasses_low_confidence(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.ict_discord_notify.ict_discord_configured", lambda _st=None: True)
    sent = {"n": 0}

    def _send(signal_id, **kwargs):
        sent["n"] += 1
        return True

    monkeypatch.setattr("app.ict_discord_notify._dedupe_send", _send)
    maybe_ict_alert(
        {
            "ict": _sample_blob(
                setup_state="INVALIDATED",
                status="INVALIDATED",
                confidence=40,
                confidence_score=40,
            )
        }
    )
    assert sent["n"] == 1
