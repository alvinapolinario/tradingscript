"""Backtest evidence — scorecard lookup, gate rules, alert + API integration."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import evidence
from app.config import Settings


def _scorecard(path: Path, strategies: dict) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": "vantage.strategy_scorecard.v1",
                "generated_utc": "2026-10-01T00:00:00+00:00",
                "data": {"symbol": "XAUUSD", "from": "2024-01-01 00:00", "to": "2026-09-30 23:55", "m5_bars": 1},
                "strategies": strategies,
            }
        ),
        encoding="utf-8",
    )
    return path


def _result(verdict: str, *, floor=None, confirmed=False, n=120, avg_r=0.2) -> dict:
    return {
        "verdict": verdict,
        "overall": {"n": n, "win_rate": 0.45, "avg_r": avg_r, "profit_factor": 1.3},
        "threshold": {"min_confidence": floor, "confirmed": confirmed},
        "confidence_buckets": [
            {"lo": 70, "hi": 80, "n": 40, "win_rate": 0.5, "avg_r": 0.35},
            {"lo": 80, "hi": 90, "n": 4, "win_rate": 1.0, "avg_r": 2.0},
        ],
    }


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    path = _scorecard(
        tmp_path / "strategy_scorecard.json",
        {
            "ict": _result("EDGE"),
            "box_theory": _result("NO_EDGE", avg_r=-0.1),
            "amd_ifvg": _result("INCONCLUSIVE", floor=75.0, confirmed=True),
            "h4_m15_fvg": _result("INSUFFICIENT_DATA", n=12),
        },
    )
    return Settings(strategy_scorecard_path=str(path), evidence_gate_enabled=True)


def test_missing_scorecard_allows_and_says_unmeasured(tmp_path: Path):
    st = Settings(strategy_scorecard_path=str(tmp_path / "nope.json"), evidence_gate_enabled=True)
    ev = evidence.strategy_evidence("ict", 80, st)
    assert ev["allowed"] is True and ev["measured"] is False and ev["reason"] == "no_scorecard"
    assert "Not measured" in evidence.evidence_text(ev)


def test_gate_rules(settings: Settings):
    assert evidence.strategy_evidence("ict", 50, settings)["allowed"] is True
    assert evidence.strategy_evidence("box_theory", 95, settings)["allowed"] is False
    assert evidence.strategy_evidence("amd_ifvg", 70, settings)["allowed"] is False
    assert evidence.strategy_evidence("amd_ifvg", 80, settings)["allowed"] is True
    h4 = evidence.strategy_evidence("h4_m15_fvg", 10, settings)
    assert h4["allowed"] is True and h4["measured"] is False
    assert evidence.strategy_evidence("unknown", 90, settings)["reason"] == "not_in_scorecard"


def test_bucket_needs_enough_trades(settings: Settings):
    assert evidence.strategy_evidence("ict", 75, settings)["bucket"]["n"] == 40
    assert evidence.strategy_evidence("ict", 85, settings)["bucket"] is None  # only 4 trades


def test_gate_only_blocks_when_enabled(settings: Settings):
    send, ev = evidence.gate("box_theory", 90, settings)
    assert send is False and ev["verdict"] == "NO_EDGE"
    off = settings.model_copy(update={"evidence_gate_enabled": False})
    send, ev = evidence.gate("box_theory", 90, off)
    assert send is True and ev["allowed"] is False


def test_evidence_text(settings: Settings):
    text = evidence.evidence_text(evidence.strategy_evidence("ict", 75, settings))
    assert "EDGE · 120 trades · 45% win · +0.20R avg" in text
    assert "Confidence 70–80: 40 trades, +0.35R avg" in text


def test_ict_trade_alert_blocked_or_annotated(monkeypatch, settings: Settings):
    from app import ict_discord_notify as ict

    sent: list[list[dict]] = []
    monkeypatch.setattr(ict, "ict_discord_configured", lambda _st=None: True)
    monkeypatch.setattr(ict, "_dedupe_send", lambda sid, **kw: sent.append(kw["fields"]) or True)
    monkeypatch.setattr(evidence, "get_settings", lambda: settings)
    blob = {
        "valid": True,
        "gold_symbol_valid": True,
        "symbol": "XAUUSD",
        "setup_state": "TRIGGERED",
        "decision": "BUY",
        "confidence": 82,
        "setup_id": "ICT-1",
        "state_changed": True,
    }
    ict.reset_state_for_tests()
    ict.maybe_ict_alert({"ict": blob})
    assert sent and sent[-1][-1]["name"] == "Backtest evidence"

    # Same alert, but the scorecard now says ICT has no edge → suppressed.
    _scorecard(Path(settings.strategy_scorecard_path), {"ict": _result("NO_EDGE", avg_r=-0.2)})
    evidence._cache.update(path=None, mtime=None, data=None)
    sent.clear()
    ict.reset_state_for_tests()
    ict.maybe_ict_alert({"ict": {**blob, "setup_id": "ICT-2"}})
    assert sent == []


def test_scorecard_api(monkeypatch, settings: Settings):
    from app.main import app

    monkeypatch.setattr(evidence, "get_settings", lambda: settings)
    body = TestClient(app).get("/api/v1/evidence/scorecard").json()
    assert body["available"] is True and body["gate_enabled"] is True
    assert body["strategies"]["box_theory"]["verdict"] == "NO_EDGE"
