"""Demo execution queue — API tests."""
from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import execution_queue as eq
from app.config import get_settings
from app.main import app
from app.monitor_state import monitor_store

client = TestClient(app)

SAMPLE_SWING = {
    "module": "swing_strategy",
    "version": "1.0",
    "valid": True,
    "gold_symbol_valid": True,
    "symbol": "XAUUSD",
    "trade_mode": "SWING",
    "trend": "Bullish",
    "confidence": 91.0,
    "signal": "STRONG SWING BUY",
    "entry_quality": "Excellent",
    "stop_loss": 4016.80,
    "tp1": 4050.0,
    "tp2": 4068.0,
    "tp3": 4090.0,
    "eval_bar_m5": int(time.time()) - 60,
}

SAMPLE_SCALP = {
    **SAMPLE_SWING,
    "trade_mode": "SCALPING",
    "signal": "SCALP BUY",
    "confidence": 78.0,
    "entry_quality": "Average",
    "stop_loss": 4035.0,
    "tp1": 4042.0,
}

WEAK_SWING = {
    **SAMPLE_SWING,
    "signal": "SWING BUY",
    "confidence": 70.0,
    "entry_quality": "Average",
}


def _auth_headers() -> dict[str, str]:
    token = get_settings().local_api_token
    return {"Authorization": f"Bearer {token}"}


def _monitor_with_swing(swing: dict) -> None:
    monitor_store.record_heartbeat(
        {
            "symbol": "XAUUSD",
            "bid": 4040.0,
            "ask": 4040.2,
            "digits": 2,
            "connected": True,
            "swing_strategy": swing,
            "swing_strategy_supported": True,
        }
    )


@pytest.fixture()
def tmp_exec_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "execution_ledger.db"
    monkeypatch.setattr(eq, "_DB_PATH", db)
    monkeypatch.setattr(eq, "_DATA_DIR", tmp_path)
    eq.init_db()
    return db


def test_execution_next_offline_empty(tmp_exec_db):
    monitor_store.select_symbol("ZZEXECOFF")
    r = client.get("/api/v1/execution/next?symbol=XAUUSD", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["demo_execution"] is True
    assert body["has_signal"] is False


def test_execution_next_strong_signal(tmp_exec_db):
    _monitor_with_swing(SAMPLE_SWING)
    r = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SWING", headers=_auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body["has_signal"] is True
    order = body["order"]
    assert order["side"] == "BUY"
    assert order["stop_loss"] == 4016.80
    assert order["take_profit"] == 4050.0
    assert order["signal_id"]


def test_execution_next_scalping_signal(tmp_exec_db):
    _monitor_with_swing(SAMPLE_SCALP)
    r = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SCALPING", headers=_auth_headers())
    body = r.json()
    assert body["has_signal"] is True
    assert body["trade_mode"] == "SCALPING"
    assert body["order"]["side"] == "BUY"


def test_execution_mode_mismatch(tmp_exec_db):
    _monitor_with_swing(SAMPLE_SWING)
    r = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SCALPING", headers=_auth_headers())
    body = r.json()
    assert body["has_signal"] is False
    assert body["reason"] == "trade_mode_mismatch"


def test_execution_next_rejects_non_strong(tmp_exec_db):
    _monitor_with_swing(WEAK_SWING)
    r = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SWING", headers=_auth_headers())
    body = r.json()
    assert body["has_signal"] is False
    assert body["reason"] == "signal_not_allowed_for_mode"


def test_execution_dedup_pending(tmp_exec_db):
    _monitor_with_swing(SAMPLE_SWING)
    h = _auth_headers()
    r1 = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SWING", headers=h)
    r2 = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SWING", headers=h)
    id1 = r1.json()["order"]["signal_id"]
    id2 = r2.json()["order"]["signal_id"]
    assert id1 == id2
    items = eq.list_history()
    assert len(items) == 1
    assert items[0]["status"] == "PENDING"


def test_execution_ack_filled(tmp_exec_db):
    _monitor_with_swing(SAMPLE_SWING)
    h = _auth_headers()
    nxt = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SWING", headers=h).json()
    sig_id = nxt["order"]["signal_id"]
    ack = client.post(
        "/api/v1/execution/ack",
        json={"signal_id": sig_id, "status": "FILLED", "ticket": 12345, "reason": "ok"},
        headers=h,
    )
    assert ack.status_code == 200
    assert ack.json()["signal"]["status"] == "FILLED"
    assert ack.json()["signal"]["ticket"] == 12345
    # Same swing should not re-fire
    again = client.get("/api/v1/execution/next?symbol=XAUUSD&mode=SWING", headers=h).json()
    assert again["has_signal"] is False
    assert again["reason"] == "already_filled"


def test_execution_history_endpoint(tmp_exec_db):
    _monitor_with_swing(SAMPLE_SWING)
    client.get("/api/v1/execution/next?symbol=XAUUSD", headers=_auth_headers())
    hist = client.get("/api/v1/execution/history?limit=10")
    assert hist.status_code == 200
    body = hist.json()
    assert body["demo_execution"] is True
    assert body["count"] >= 1
    assert "summary" in body


def test_execution_next_requires_auth(tmp_exec_db):
    r = client.get("/api/v1/execution/next?symbol=XAUUSD")
    assert r.status_code == 401
