"""Step 14 — regression runner markers and ICT stack smoke checks."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Strategy status + static desk pages exercised in full regression
STRATEGY_STATUS_PATHS = [
    "/api/v1/ict/status",
    "/api/v1/box-theory/status",
    "/api/v1/amd-ifvg/status",
    "/api/v1/liquidity-grab/status",
    "/api/v1/gold-smc/status",
    "/api/v1/swing-strategy/status",
    "/api/v1/breakout-structure/status",
    "/api/v1/market-state/status",
    "/api/v1/pullback/status",
    "/api/v1/confluence/status",
]

STRATEGY_STATIC_PAGES = [
    "/ict",
    "/box-theory",
    "/amd-ifvg",
    "/liquidity-grab",
    "/gold-smc",
    "/swing-strategy",
    "/breakout-structure",
    "/market-state",
    "/pullback",
]


@pytest.mark.parametrize("path", STRATEGY_STATUS_PATHS)
def test_strategy_status_endpoints_reachable(path: str):
    r = TestClient(app).get(path)
    assert r.status_code == 200
    body = r.json()
    assert body.get("advisory_only") is True


@pytest.mark.parametrize("path", STRATEGY_STATIC_PAGES)
def test_strategy_static_pages_load(path: str):
    r = TestClient(app).get(path)
    assert r.status_code == 200
    assert len(r.text) > 100
