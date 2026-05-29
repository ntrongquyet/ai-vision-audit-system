import json

from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.core.prompts import VISION_SYSTEM_PROMPT
from app.config import get_settings
from app.models.schemas import VisionTagResult


@with_retry
async def analyze_image(image_url: str) -> VisionTagResult:
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().vision_model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this site survey photo. Return JSON {tags, detailed_description}."},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]},
        ],
    )
    raw = resp.choices[0].message.content
    return VisionTagResult.model_validate(json.loads(raw))
