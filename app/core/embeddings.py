from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.config import get_settings


@with_retry
async def embed_text(text: str) -> list[float]:
    settings = get_settings()
    client = get_ai_client()
    # Force the output to EMBEDDING_DIM (MRL truncation) so it matches the
    # vector(EMBEDDING_DIM) DB column regardless of the model's native size
    # (e.g. gemini-embedding outputs 3072 by default; we request 1536).
    resp = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dim,
    )
    return list(resp.data[0].embedding)
