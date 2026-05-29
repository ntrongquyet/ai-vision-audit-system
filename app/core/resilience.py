import asyncio
from functools import lru_cache

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings


# EX-01 / NFR 5.2: retry 3 lần, exponential backoff
def with_retry(func):
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
        before_sleep=lambda rs: logger.warning(
            f"AI call retry #{rs.attempt_number}: {rs.outcome.exception()}"
        ),
    )(func)


@lru_cache
def get_semaphore() -> asyncio.Semaphore:
    # NFR 5.1: tối đa 5 ảnh gọi AI song song
    return asyncio.Semaphore(get_settings().ai_max_concurrency)
