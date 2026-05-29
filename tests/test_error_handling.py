import httpx, pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from openai import APIError

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret")
    from app.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)

def _api_error():
    return APIError("provider overloaded",
                    request=httpx.Request("POST", "http://9router/v1/chat/completions"),
                    body=None)

def test_audit_ai_failure_returns_503(client):
    # route-level run_audit raises an OpenAI APIError (simulating exhausted retries)
    with patch("app.api.routes_audit.run_audit", AsyncMock(side_effect=_api_error())):
        r = client.post("/api/v1/projects/audit",
                        headers={"X-API-KEY": "secret"},
                        json={"project_id": "P", "scope_text": "paint walls"})
    assert r.status_code == 503
    assert "thử lại" in r.json()["detail"]
