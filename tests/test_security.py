import pytest
from fastapi import HTTPException
from app.security import require_api_key


def test_valid_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret"); _reset()
    assert require_api_key("secret") is None


def test_invalid_key(monkeypatch):
    monkeypatch.setenv("APP_API_KEY", "secret"); _reset()
    with pytest.raises(HTTPException) as e:
        require_api_key("wrong")
    assert e.value.status_code == 401


def _reset():
    from app.config import get_settings
    get_settings.cache_clear()
