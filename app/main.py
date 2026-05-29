import sys
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from openai import APIError
from loguru import logger
from app.config import get_settings
from app.db.engine import engine
from app.api import (routes_index, routes_status, routes_audit, routes_chat,
                     routes_uploads, routes_extract)

_settings = get_settings()

logger.remove()
logger.add(sys.stderr, level=_settings.log_level, format="{time} {level} {message}")

app = FastAPI(
    title="AI Vision Audit System",
    docs_url="/docs" if _settings.enable_docs else None,
    redoc_url="/redoc" if _settings.enable_docs else None,
    openapi_url="/openapi.json" if _settings.enable_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-KEY", "Content-Type"],
)


@app.exception_handler(APIError)
async def ai_provider_error_handler(request: Request, exc: APIError):
    logger.error("AI provider error after retries: status={} message={}", exc.status_code, exc.message)
    return JSONResponse(
        status_code=503,
        content={"detail": "Hệ thống đang bận xử lý dữ liệu lớn, vui lòng thử lại sau 1 phút."},
    )


@app.get("/health")
async def health():
    checks: dict = {}
    overall = "ok"

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"
        overall = "degraded"

    s = get_settings()
    checks["ai_configured"] = bool(s.ai_base_url and s.ai_api_key)

    return JSONResponse(
        content={"status": overall, "checks": checks},
        status_code=200 if overall == "ok" else 503,
    )


app.include_router(routes_index.router)
app.include_router(routes_status.router)
app.include_router(routes_audit.router)
app.include_router(routes_chat.router)
app.include_router(routes_uploads.router)
app.include_router(routes_extract.router)

os.makedirs(_settings.upload_dir, exist_ok=True)
app.mount("/files", StaticFiles(directory=_settings.upload_dir), name="files")
app.mount("/", StaticFiles(directory="app/static", html=True), name="ui")
