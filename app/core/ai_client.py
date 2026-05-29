from functools import lru_cache

from openai import AsyncOpenAI

from app.config import get_settings


@lru_cache
def get_ai_client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(base_url=s.ai_base_url, api_key=s.ai_api_key)
