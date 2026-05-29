import pytest
from unittest.mock import AsyncMock, patch
from app.core import extraction


def _fake_client(text):
    fake = AsyncMock()
    fake.chat.completions.create.return_value = type("R", (), {
        "choices": [type("C", (), {"message": type("M", (), {"content": text})()})()]})()
    return fake


@pytest.mark.asyncio
async def test_ocr_image_bytes():
    with patch("app.core.extraction.get_ai_client",
               return_value=_fake_client("# Quote\nPaint walls")):
        out = await extraction.ocr_image_bytes(b"\xff\xd8fakejpeg", "image/jpeg")
    assert "Paint walls" in out


@pytest.mark.asyncio
async def test_extract_text_routes_image_to_ocr():
    with patch("app.core.extraction.ocr_image_bytes",
               AsyncMock(return_value="extracted text")) as m:
        out = await extraction.extract_text("photo.jpg", b"bytes", "image/jpeg")
    assert out == "extracted text"
    assert m.await_count == 1


@pytest.mark.asyncio
async def test_extract_text_pdf_with_embedded_text(tmp_path):
    # build a real one-page PDF with selectable text via PyMuPDF
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Scope of Works: paint all timber weatherboard walls.")
    pdf_bytes = doc.tobytes()
    # embedded-text path must NOT call OCR
    with patch("app.core.extraction.ocr_image_bytes",
               AsyncMock(side_effect=AssertionError("OCR should not run"))):
        out = await extraction.extract_text("quote.pdf", pdf_bytes, "application/pdf")
    assert "timber weatherboard" in out
