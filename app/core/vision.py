import base64

import httpx

from app.core.ai_client import get_ai_client
from app.core.json_utils import extract_json
from app.core.resilience import with_retry
from app.core.prompts import VISION_SYSTEM_PROMPT
from app.config import get_settings
from app.models.schemas import VisionTagResult


async def _fetch_image_data_uri(image_url: str) -> str:
    """Download the image and return a base64 data URI.

    Anthropic Claude (via the OpenAI-compatible 9router gateway) cannot fetch
    remote image URLs itself — it requires the image bytes inline. We download
    the image server-side and pass it as a data URI, which the gateway forwards
    as a base64 image block. This also works for OpenAI models and for Supabase
    Storage public URLs in production.
    """
    async with httpx.AsyncClient(timeout=30) as cli:
        resp = await cli.get(image_url)
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
    b64 = base64.b64encode(resp.content).decode("ascii")
    return f"data:{content_type};base64,{b64}"


@with_retry
async def analyze_image(image_url: str) -> VisionTagResult:
    data_uri = await _fetch_image_data_uri(image_url)
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().vision_model,
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Analyze this site survey photo. Return JSON {tags, detailed_description}."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]},
        ],
    )
    raw = resp.choices[0].message.content
    return VisionTagResult.model_validate(extract_json(raw))
