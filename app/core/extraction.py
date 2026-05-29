"""Extract text from an uploaded PDF or image.

- Image (png/jpg/webp): OCR via the vision model (Claude on 9router).
- PDF: try fast text extraction (pypdf). If the PDF is scanned (little/no
  embedded text), rasterise each page (PyMuPDF) and OCR it via the vision model.

Returns Markdown-ish text the user can preview/edit before running the audit.
"""
import base64

import fitz  # PyMuPDF
from loguru import logger
from pypdf import PdfReader
import io

from app.core.ai_client import get_ai_client
from app.core.resilience import with_retry
from app.config import get_settings

OCR_PROMPT = (
    "You are an OCR engine. Extract ALL text from this document image verbatim. "
    "Preserve the structure as Markdown (use headings, bullet lists, and keep "
    "tables readable). Output ONLY the extracted text, with no commentary."
)

# A PDF page with fewer characters than this is treated as scanned → OCR.
_MIN_TEXT_CHARS = 30


@with_retry
async def ocr_image_bytes(content: bytes, content_type: str = "image/png") -> str:
    """Run the vision model as an OCR engine on raw image bytes."""
    b64 = base64.b64encode(content).decode("ascii")
    data_uri = f"data:{content_type};base64,{b64}"
    client = get_ai_client()
    resp = await client.chat.completions.create(
        model=get_settings().vision_model,
        messages=[
            {"role": "system", "content": OCR_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Extract all text from this document."},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


async def _extract_pdf(content: bytes) -> str:
    # 1) fast path: embedded text
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [(p.extract_text() or "").strip() for p in reader.pages]
        text = "\n\n".join(t for t in pages if t)
        if len(text) >= _MIN_TEXT_CHARS:
            return text
    except Exception as e:  # corrupt/unsupported → fall back to OCR
        logger.warning(f"pypdf extraction failed, falling back to OCR: {e}")

    # 2) scanned PDF: rasterise each page and OCR it
    doc = fitz.open(stream=content, filetype="pdf")
    out: list[str] = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        png = pix.tobytes("png")
        out.append(await ocr_image_bytes(png, "image/png"))
    return "\n\n".join(t for t in out if t).strip()


async def extract_text(filename: str, content: bytes, content_type: str | None) -> str:
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if name.endswith(".pdf") or "pdf" in ctype:
        return await _extract_pdf(content)
    # treat everything else as an image
    img_type = ctype if ctype.startswith("image/") else "image/jpeg"
    return await ocr_image_bytes(content, img_type)
