from fastapi import Header, HTTPException

from app.config import get_settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().app_api_key
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-KEY")
