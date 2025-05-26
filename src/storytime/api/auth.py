from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
import os

API_KEY_NAME = "X-API-Key"
API_KEY_HEADER = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# For MVP: API keys from environment variable (comma-separated)
API_KEYS = set(k.strip() for k in os.getenv("STORYTIME_API_KEYS", "testkey").split(","))


def get_api_key(api_key_header: str = Security(API_KEY_HEADER)):
    if api_key_header in API_KEYS:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API Key",
    ) 