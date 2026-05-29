from fastapi.testclient import TestClient
from app.main import app


def test_root_serves_ui():
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "AI Vision Audit" in r.text


def test_appjs_served():
    client = TestClient(app)
    r = client.get("/app.js")
    assert r.status_code == 200
    assert "uploadAndIndex" in r.text
