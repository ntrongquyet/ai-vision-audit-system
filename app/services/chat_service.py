from app.config import get_settings
from app.db.engine import SessionLocal
from app.db import repositories as repo
from app.core.embeddings import embed_text
from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.models.schemas import ChatResponse


@with_retry
async def _answer(question: str, context: str) -> str:
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().reasoning_model,
        messages=[
            {"role": "system", "content":
             "Answer the user's question about a building site using ONLY the provided photo "
             "descriptions. Be concise (2-3 sentences)."},
            {"role": "user", "content": f"PHOTOS:\n{context}\n\nQUESTION: {question}"},
        ],
    )
    return resp.choices[0].message.content


async def answer(project_id: str, user_question: str) -> ChatResponse:
    s_cfg = get_settings()
    query_vec = await embed_text(user_question)
    async with SessionLocal() as s:
        matches = await repo.match_visual_indices(
            s, project_id, query_vec, s_cfg.match_threshold, s_cfg.match_count)
    if not matches:
        return ChatResponse(answer_text="No relevant photos found for this question.",
                            reference_image_urls=[])
    context = "\n".join(f"- ({m['image_url']}) {m['detailed_description']}" for m in matches)
    answer_text = await _answer(user_question, context)
    return ChatResponse(answer_text=answer_text,
                        reference_image_urls=[m["image_url"] for m in matches])
