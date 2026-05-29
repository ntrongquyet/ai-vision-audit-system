import pytest

from app.core.resilience import with_retry


@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    calls = {"n": 0}

    @with_retry
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("429 rate limit")
        return "ok"

    assert await flaky() == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_retry_gives_up_after_3():
    @with_retry
    async def always_fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await always_fail()
