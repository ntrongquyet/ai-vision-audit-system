import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError
from loguru import logger
from app.config import get_settings
from app.api import routes_index, routes_status, routes_audit, routes_chat, routes_uploads

app = FastAPI(title="AI Vision Audit System")


@app.exception_handler(APIError)
async def ai_provider_error_handler(request: Request, exc: APIError):
    logger.error(f"AI provider error after retries: {exc!r}")
    return JSONResponse(
        status_code=503,
        content={"detail": "Hệ thống đang bận xử lý dữ liệu lớn, vui lòng thử lại sau 1 phút."},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(routes_index.router)
app.include_router(routes_status.router)
app.include_router(routes_audit.router)
app.include_router(routes_chat.router)
app.include_router(routes_uploads.router)

_settings = get_settings()
os.makedirs(_settings.upload_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=_settings.upload_dir), name="files")
app.mount("/", StaticFiles(directory="app/static", html=True), name="ui")
