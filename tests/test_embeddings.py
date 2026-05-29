import pytest
from unittest.mock import AsyncMock, patch
from app.core import embeddings


@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    fake = AsyncMock()
    fake.embeddings.create.return_value = type("R", (), {
        "data": [type("D", (), {"embedding": [0.1, 0.2, 0.3]})()]})()
    with patch("app.core.embeddings.get_ai_client", return_value=fake):
        vec = await embeddings.embed_text("hello")
    assert vec == [0.1, 0.2, 0.3]
