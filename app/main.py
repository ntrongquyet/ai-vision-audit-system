import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.api import routes_index, routes_status, routes_audit, routes_chat, routes_uploads

app = FastAPI(title="AI Vision Audit System")


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
