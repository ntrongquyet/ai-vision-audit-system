import json
import re


def extract_json(raw: str | None) -> dict:
    """Parse a JSON object from an LLM response that may be wrapped.

    Some providers (e.g. Anthropic Claude via an OpenAI-compatible gateway)
    ignore ``response_format`` and return the JSON inside a markdown code
    fence (```json ... ```), or with leading/trailing prose. This strips the
    fence and, as a fallback, slices from the first ``{`` to the last ``}``
    before parsing.
    """
    if not raw or not raw.strip():
        raise ValueError("empty AI response")
    s = raw.strip()
    # strip a leading ```json / ``` fence and trailing ```
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    # fallback: take the outermost { ... } if there is surrounding prose
    if not s.startswith("{"):
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end != -1 and end > start:
            s = s[start:end + 1]
    return json.loads(s)
