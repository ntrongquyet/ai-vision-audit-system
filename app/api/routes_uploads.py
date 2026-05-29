import os
import uuid
from fastapi import APIRouter, UploadFile, Depends
from app.security import require_api_key
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["uploads"])


@router.post("/uploads", dependencies=[Depends(require_api_key)])
async def upload(files: list[UploadFile]):
    s = get_settings()
    os.makedirs(s.upload_dir, exist_ok=True)
    urls = []
    for f in files:
        name = f"{uuid.uuid4().hex}_{f.filename}"
        path = os.path.join(s.upload_dir, name)
        with open(path, "wb") as out:
            out.write(await f.read())
        urls.append(f"{s.upload_public_base_url}/{name}")
    return {"image_urls": urls}
