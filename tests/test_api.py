import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_index_requires_key(client):
    r = client.post("/api/v1/projects/index",
                    json={"project_id": "P", "image_urls": ["u"]})
    assert r.status_code == 401


def test_index_empty_urls_422(client):
    r = client.post("/api/v1/projects/index",
                    headers={"X-API-KEY": "secret"},
                    json={"project_id": "P", "image_urls": []})
    assert r.status_code == 422  # pydantic validation


def test_index_accepts(client):
    with patch("app.api.routes_index.job_service.create", AsyncMock(return_value="job-1")), \
         patch("app.api.routes_index.run_indexing_job", AsyncMock()):
        r = client.post("/api/v1/projects/index",
                        headers={"X-API-KEY": "secret"},
                        json={"project_id": "P", "image_urls": ["u1", "u2"]})
    assert r.status_code == 202
    assert r.json()["total_images"] == 2
