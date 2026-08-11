"""News / Macro desk — static page + route audits (Step 10)."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"
SHELL = STATIC / "shell.js"

client = TestClient(app)


def test_market_news_page_route():
    r = client.get("/market-news")
    assert r.status_code == 200
    assert "News / Macro Intelligence" in r.text


def test_market_news_html_sections():
    html = (STATIC / "market-news.html").read_text(encoding="utf-8")
    for needle in (
        "data-nav=\"market-news\"",
        "/api/v1/market-news/status",
        "/api/v1/market-news/analyze",
        "Currency bias heatmap",
        "Economic calendar",
        "Session timeline",
    ):
        assert needle in html


def test_shell_nav_includes_market_news():
    text = SHELL.read_text(encoding="utf-8")
    assert 'id: "market-news"' in text
    assert 'href: "/market-news"' in text
    assert "News / Macro" in text
