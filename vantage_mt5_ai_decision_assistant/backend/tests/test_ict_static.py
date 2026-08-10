"""ICT static page smoke test."""
from fastapi.testclient import TestClient

from app.main import app


def test_ict_page_loads():
    r = TestClient(app).get("/ict")
    assert r.status_code == 200
    assert "ICT Strategy" in r.text
    assert "/api/v1/ict/status" in r.text
    assert "Setup progress" in r.text
    assert "renderProgress" in r.text
