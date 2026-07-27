"""API auth, malformed payload, and advisory enforcement tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.main import app
from app.config import get_settings
from conftest import base_payload

client = TestClient(app)
TOKEN = get_settings().local_api_token
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["advisory_only"] is True


def test_analyze_unauthorized():
    r = client.post("/api/v1/analyze", json=base_payload())
    assert r.status_code == 401


def test_analyze_ok():
    r = client.post("/api/v1/analyze", json=base_payload(), headers=AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "WAIT_FOR_RETEST"
    assert body["advisory_only"] is True


def test_malformed_missing_symbol():
    bad = base_payload()
    del bad["symbol"]
    r = client.post("/api/v1/analyze", json=bad, headers=AUTH)
    assert r.status_code == 422


def test_rejects_non_advisory_mode():
    bad = base_payload(mode="auto_trade")
    r = client.post("/api/v1/analyze", json=bad, headers=AUTH)
    assert r.status_code == 400


def test_no_openai_key_required_for_rule_engine():
    # Rule engine works with USE_LLM=false and no cloud key
    r = client.post("/api/v1/analyze", json=base_payload(), headers=AUTH)
    assert r.status_code == 200
