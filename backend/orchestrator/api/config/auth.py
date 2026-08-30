"""API Key Authentication and Persona Resolution (Req 8)."""

import os
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

PERSONA_KEYS = {
    os.getenv("EXEC_API_KEY", "exec-demo-key"): "executive",
    os.getenv("ANALYST_API_KEY", "analyst-demo-key"): "analyst",
}

api_key_header = APIKeyHeader(name="X-Api-Key", auto_error=False)


def resolve_persona(x_api_key: Optional[str] = Security(api_key_header)) -> str:
    """Validate API key and return server-side persona. Raises 401 if key missing/invalid."""
    if not x_api_key or x_api_key not in PERSONA_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")
    return PERSONA_KEYS[x_api_key]
