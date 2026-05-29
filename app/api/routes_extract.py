from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.security import require_api_key
from app.core.extraction import extract_text

router = APIRouter(prefix="/api/v1", tags=["extract"])


@router.post("/extract-text", dependencies=[Depends(require_api_key)])
async def extract(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    text = await extract_text(file.filename or "", content, file.content_type)
    return {"filename": file.filename, "text": text}
