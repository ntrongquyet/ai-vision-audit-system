import os
import uuid
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from app.security import require_api_key
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["uploads"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}


@router.post("/uploads", dependencies=[Depends(require_api_key)])
async def upload(files: list[UploadFile]):
    s = get_settings()

    if len(files) > s.max_upload_count:
        raise HTTPException(400, f"Tối đa {s.max_upload_count} file mỗi lần upload")

    os.makedirs(s.upload_dir, exist_ok=True)
    urls = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(400, f"Định dạng file không được phép: {ext or '(không có extension)'}")

        content = await f.read()
        max_bytes = s.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(413, f"File quá lớn (tối đa {s.max_upload_size_mb}MB)")

        name = f"{uuid.uuid4().hex}{ext}"
        path = os.path.join(s.upload_dir, name)
        with open(path, "wb") as out:
            out.write(content)
        urls.append(f"{s.upload_public_base_url}/{name}")

    return {"image_urls": urls}
