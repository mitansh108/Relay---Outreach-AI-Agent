"""Verify sessions with Supabase Auth; never trust browser-provided user IDs."""
import os
from uuid import UUID

import httpx
from fastapi import HTTPException, Request


def supabase_enabled():
    mode = os.getenv("COPILOT_AUTH_MODE", "demo")
    if mode not in {"demo", "supabase"}:
        raise RuntimeError("COPILOT_AUTH_MODE must be demo or supabase")
    return mode == "supabase"


def identity(request: Request):
    cached = getattr(request.state, "identity", None)
    if cached:
        return cached
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not url.startswith("https://") or not key:
        raise HTTPException(503, "Supabase authentication is not configured")
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer ") or not authorization[7:].strip():
        raise HTTPException(401, "Sign in to continue")
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{url}/auth/v1/user", headers={"apikey": key, "Authorization": authorization})
        if response.status_code in (401, 403):
            raise HTTPException(401, "Your session has expired. Sign in again")
        response.raise_for_status()
        user = response.json()
        UUID(user["id"])
        if user.get("is_anonymous"):
            raise HTTPException(403, "Use a registered account")
    except (httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, "Could not verify your session. Try again") from None
    request.state.identity = {"id": user["id"], "email": user.get("email", "")}
    return request.state.identity
