from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
