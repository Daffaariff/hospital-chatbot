"""Bearer API-key check for admin endpoints."""
from fastapi import Header, HTTPException

from app.core.config import settings


def require_api_key(authorization: str = Header(default="")) -> None:
    if not settings.api_keys:
        raise HTTPException(503, "admin endpoints disabled: set API_KEYS")
    if authorization.removeprefix("Bearer ").strip() not in settings.api_keys:
        raise HTTPException(401, "invalid API key")
