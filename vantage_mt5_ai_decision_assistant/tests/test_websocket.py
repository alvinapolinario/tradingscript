"""WebSocket monitor smoke test."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings

TOKEN = get_settings().local_api_token
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_monitor_page_ok():
    client = TestClient(app)
    r = client.get("/monitor")
    assert r.status_code == 200
    assert "WebSocket" in r.text or "ws/monitor" in r.text


def test_websocket_snapshot():
    client = TestClient(app)
    with client.websocket_connect("/ws/monitor") as ws:
        data = ws.receive_json()
        assert data["type"] in {"snapshot", "startup", "tick", "update"}
        assert "status" in data
        assert "decision_brief" in data["status"]
        assert data["status"]["backend"]["status"] == "online"
        assert "headline" in data["status"]["decision_brief"]


def test_monitor_page_has_decision_brief():
    client = TestClient(app)
    r = client.get("/monitor")
    assert r.status_code == 200
    assert "Decision Brief" in r.text
    assert "Floating P/L vs Equity" in r.text
    assert "Trading History Calendar" in r.text
    assert "Live Logs" not in r.text
    assert "equityPie" in r.text
