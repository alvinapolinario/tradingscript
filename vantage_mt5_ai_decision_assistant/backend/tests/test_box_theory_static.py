"""Box Theory static page smoke test."""
from fastapi.testclient import TestClient

from app.main import app


def test_box_theory_page_loads():
    r = TestClient(app).get("/box-theory")
    assert r.status_code == 200
    assert "Box Theory" in r.text
    assert "box-theory/status" in r.text or "/api/v1/box-theory/status" in r.text
