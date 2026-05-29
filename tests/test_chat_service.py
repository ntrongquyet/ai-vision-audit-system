import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_chat_returns_answer_with_references():
    from app.services import chat_service as svc
    with patch("app.services.chat_service.embed_text", AsyncMock(return_value=[0.0]*1536)), \
         patch("app.services.chat_service.repo.match_visual_indices",
               AsyncMock(return_value=[{"image_url":"u1","detailed_description":"rusty roof","similarity":0.9}])), \
         patch("app.services.chat_service._answer", AsyncMock(return_value="Yes, high-access work needed.")):
        out = await svc.answer("PROJ-X", "Any high access work?")
    assert out.answer_text == "Yes, high-access work needed."
    assert out.reference_image_urls == ["u1"]

@pytest.mark.asyncio
async def test_chat_no_matches():
    from app.services import chat_service as svc
    with patch("app.services.chat_service.embed_text", AsyncMock(return_value=[0.0]*1536)), \
         patch("app.services.chat_service.repo.match_visual_indices", AsyncMock(return_value=[])):
        out = await svc.answer("PROJ-X", "anything?")
    assert out.reference_image_urls == []
