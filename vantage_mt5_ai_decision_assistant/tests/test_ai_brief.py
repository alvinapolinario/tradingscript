"""AI brief markdown + LLM analyze endpoint (mocked OpenAI)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings
from app.monitor_state import monitor_store
from app.analysis.ai_brief import build_ai_brief_markdown
from app.analysis.openai_client import LlmStatus

TOKEN = get_settings().local_api_token
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_ai_brief_markdown_contains_sections():
    client = TestClient(app)
    client.post(
        "/api/v1/heartbeat",
        json={
            "symbol": "XAUUSD",
            "currency": "USD",
            "bid": 4100.0,
            "ask": 4100.5,
            "trend": "BEARISH",
            "new_entry_decision": "NO_NEW_TRADE",
            "risk_status": "LOW",
            "bullish_pct": 30,
            "bearish_pct": 60,
            "neutral_pct": 10,
            "equity": 200,
            "floating_pl": 0,
        },
        headers=AUTH,
    )
    r = client.get("/api/v1/monitor/ai-brief")
    assert r.status_code == 200
    md = r.json()["markdown"]
    assert "Vantage MT5 Advisory Snapshot" in md
    assert "Decision matrix" in md
    assert "XAUUSD" in md
    assert "Ask ChatGPT" in md
    assert "advisory" in md.lower()


def test_ai_analyze_requires_llm_enabled():
    client = TestClient(app)
    r = client.post("/api/v1/monitor/ai-analyze", json={})
    assert r.status_code == 400


def test_ai_analyze_success_mocked():
    client = TestClient(app)
    client.post(
        "/api/v1/heartbeat",
        json={"symbol": "BTCUSD", "currency": "USD", "bid": 65000, "ask": 65050},
        headers=AUTH,
    )
    client.post("/api/v1/monitor/select-symbol", json={"symbol": "BTCUSD"})

    fake = {
        "status": "ok",
        "model": "gpt-4o-mini",
        "analysis_markdown": "Summary bullets...\nAdvisory only — not an order to trade.",
        "symbol": "BTCUSD",
        "cached": False,
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }
    ready = LlmStatus(
        enabled=True, configured=True, model="gpt-4o-mini", ready=True, detail="Ready"
    )

    with patch("app.analysis.openai_client.llm_status", return_value=ready):
        with patch("app.analysis.openai_client.analyze_with_openai", return_value=fake):
            r = client.post("/api/v1/monitor/ai-analyze", json={"bypass_cache": True})

    assert r.status_code == 200
    body = r.json()
    assert "Summary bullets" in body["analysis_markdown"]
    assert body["model"] == "gpt-4o-mini"
    assert "snapshot_markdown" in body


def test_build_brief_helper_direct():
    status = monitor_store.status()
    md = build_ai_brief_markdown(status)
    assert "Vantage MT5 Advisory Snapshot" in md
