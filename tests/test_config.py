import os
from app.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://x/v1")
    monkeypatch.setenv("AI_API_KEY", "k")
    monkeypatch.setenv("APP_API_KEY", "app-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    # _env_file=None makes this hermetic: it ignores the local .env so the
    # assertions test the field DEFAULTS, not whatever is configured locally.
    s = Settings(_env_file=None)
    assert s.embedding_dim == 1536          # default
    assert s.ai_max_concurrency == 5        # default
    assert s.app_api_key == "app-key"
