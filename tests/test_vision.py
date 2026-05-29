import json, pytest
from unittest.mock import AsyncMock, patch
from app.core import vision

@pytest.mark.asyncio
async def test_analyze_image_parses_json():
    fake = AsyncMock()
    fake.chat.completions.create.return_value = type("R", (), {
        "choices": [type("C", (), {"message": type("M", (), {
            "content": json.dumps({"tags": ["rust", "roof"],
                                   "detailed_description": "rusty corrugated roof"})})()})()]
    })()
    with patch("app.core.vision.get_ai_client", return_value=fake), \
         patch("app.core.vision._fetch_image_data_uri",
               AsyncMock(return_value="data:image/jpeg;base64,AAAA")):
        res = await vision.analyze_image("http://x/img.jpg")
    assert res.tags == ["rust", "roof"]
    assert "rusty" in res.detailed_description
