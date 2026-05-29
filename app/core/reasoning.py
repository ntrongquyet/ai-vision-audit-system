from loguru import logger

from app.config import get_settings
from app.core.ai_client import get_ai_client
from app.core.json_utils import extract_json
from app.core.prompts import REASONING_SYSTEM_PROMPT
from app.core.resilience import with_retry
from app.models.schemas import AuditReportSchema


@with_retry
async def _call(messages) -> str:
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().reasoning_model,
        response_format={"type": "json_object"},
        messages=messages,
    )
    return resp.choices[0].message.content


async def run_audit(context_block: str, scope_text: str) -> AuditReportSchema:
    user = f"<context>\n{context_block}\n</context>\n<scope_text>\n{scope_text}\n</scope_text>"
    messages = [
        {"role": "system", "content": REASONING_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    raw = await _call(messages)
    try:
        return AuditReportSchema.model_validate(extract_json(raw))
    except Exception as e:
        logger.warning(f"Audit JSON parse failed, repair retry: {e}")
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user",
            "content": "Your output was not valid for the required schema. "
                       "Return ONLY corrected JSON, no prose."})
        raw2 = await _call(messages)
        return AuditReportSchema.model_validate(extract_json(raw2))
