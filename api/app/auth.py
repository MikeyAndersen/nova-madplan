import secrets

from fastapi import Header, HTTPException

from . import config


def require_api_token(authorization: str = Header(default="")) -> None:
    """Bearer-auth for /api/* (spec §3.1). Fejler lukket hvis token ikke er sat."""
    if not config.LIFEHUB_API_TOKEN:
        raise HTTPException(status_code=503, detail="LIFEHUB_API_TOKEN is not configured")
    expected = f"Bearer {config.LIFEHUB_API_TOKEN}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")
