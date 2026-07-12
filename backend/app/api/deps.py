"""Shared API dependencies."""

from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_admin_key(x_api_key: str = Header(default="")) -> None:
    """Guard for admin/field-ops endpoints (X-API-Key header)."""
    settings = get_settings()
    if not settings.admin_api_key or x_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
        )
