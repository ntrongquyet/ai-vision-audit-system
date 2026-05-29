from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_postgres_scheme(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    ai_base_url: str
    ai_api_key: str
    vision_model: str = "gemini-2.0-flash"
    reasoning_model: str = "claude-3-5-sonnet"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    ai_max_concurrency: int = 5
    ai_batch_size: int = 5

    app_api_key: str
    database_url: str
    upload_dir: str = "uploads"
    upload_public_base_url: str = "http://localhost:8000/files"
    match_threshold: float = 0.7
    match_count: int = 3

    enable_docs: bool = True
    allowed_origins: list[str] = ["http://localhost:8000"]
    max_upload_size_mb: int = 10
    max_upload_count: int = 20
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
