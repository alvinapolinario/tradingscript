"""H4→M15 FVG Discord notification tests."""
from app.h4_m15_fvg_discord_notify import (
    _dedupe_send,
    maybe_h4_m15_fvg_alert,
    reset_state_for_tests,
)


def _sample_module(**overrides):
    setup = {
        "setup_id": "H4M15-EURUSD-B-200000",
        "symbol": "EURUSD",
        "direction": "BULLISH",
        "state": "ENTRY_READY",
        "decision": "ENTRY_READY",
        "score": 82,
        "grade": "HIGH",
        "state_changed": True,
        "htf_location": {"lower": 1.0845, "upper": 1.0850, "mitigation_percent": 62},
        "liquidity": {"sweep_detected": True, "type": "SELL_SIDE"},
        "displacement": {"confirmed": True, "score": 84},
        "structure": {"mss_confirmed": True, "broken_level": 1.08532},
        "entry_fvg": {"lower": 1.08485, "upper": 1.08505},
        "entry_price": 1.08495,
        "structural_stop": 1.08410,
    }
    base = {
        "module": "h4_m15_fvg",
        "valid": True,
        "symbol": "EURUSD",
        "primary": setup,
        "setups": [setup],
    }
    base.update(overrides)
    return {"h4_m15_fvg": base}


def test_duplicate_discord_prevention(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.h4_m15_fvg_discord_notify.h4_m15_fvg_discord_configured", lambda _st=None: True)
    monkeypatch.setattr("app.h4_m15_fvg_discord_notify._send_embed", lambda **kwargs: (True, "sent"))
    sid = "H4M15-EURUSD-B-200000|ENTRY_READY"
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is True
    assert _dedupe_send(sid, title="t", description="d", fields=[], color=1) is False


def test_maybe_alert_skips_when_not_configured(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.h4_m15_fvg_discord_notify.h4_m15_fvg_discord_configured", lambda _st=None: False)
    sent = {"n": 0}

    def _send(*a, **k):
        sent["n"] += 1

    monkeypatch.setattr("app.h4_m15_fvg_discord_notify._dedupe_send", _send)
    maybe_h4_m15_fvg_alert(_sample_module())
    assert sent["n"] == 0


def test_maybe_alert_entry_ready(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.h4_m15_fvg_discord_notify.h4_m15_fvg_discord_configured", lambda _st=None: True)
    sent: list[str] = []
    monkeypatch.setattr(
        "app.h4_m15_fvg_discord_notify._dedupe_send",
        lambda sid, **kw: sent.append(sid) or True,
    )
    maybe_h4_m15_fvg_alert(_sample_module())
    assert sent == ["H4M15-EURUSD-B-200000|ENTRY_READY"]


def test_maybe_alert_skips_without_state_change(monkeypatch):
    reset_state_for_tests()
    monkeypatch.setattr("app.h4_m15_fvg_discord_notify.h4_m15_fvg_discord_configured", lambda _st=None: True)
    sent: list[str] = []
    monkeypatch.setattr(
        "app.h4_m15_fvg_discord_notify._dedupe_send",
        lambda sid, **kw: sent.append(sid) or True,
    )
    mod = _sample_module()
    mod["h4_m15_fvg"]["primary"]["state_changed"] = False
    mod["h4_m15_fvg"]["setups"][0]["state_changed"] = False
    maybe_h4_m15_fvg_alert(mod)
    assert sent == []
