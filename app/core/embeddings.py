from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.config import get_settings


@with_retry
async def embed_text(text: str) -> list[float]:
    client = get_ai_client()
    resp = await client.embeddings.create(
        model=get_settings().embedding_model, input=text)
    return list(resp.data[0].embedding)
