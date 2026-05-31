"""Auth HTTP endpoints for Radio-TTY.

POST /auth/login      — verify credentials, issue session token
POST /auth/logout     — revoke session token
GET  /auth/me         — return current user profile (sensitive fields stripped)
GET  /auth/profiles   — public list of profiles for the login screen

These are mounted under /auth by server.py after startup.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from backend.persistence.users import SENSITIVE_PROFILE_FIELDS

router = APIRouter()

# Populated by server.py via init() after singletons are ready.
_users_store = None
_token_store = None


def init(users_store, token_store) -> None:
    global _users_store, _token_store
    _users_store = users_store
    _token_store = token_store


def _require_token(authorization: str | None) -> str:
    """Extract and validate Bearer token; return user_id or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.removeprefix("Bearer ")
    if _token_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    user_id = _token_store.validate(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Token invalid or expired")
    return user_id


def _safe(u: dict) -> dict:
    return {k: v for k, v in u.items() if k not in SENSITIVE_PROFILE_FIELDS}


class LoginRequest(BaseModel):
    display_name: str
    password: str


@router.post("/login")
async def login(body: LoginRequest):
    if _users_store is None or _token_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")

    # Find user by display_name (case-insensitive)
    user = next(
        (u for u in _users_store.get_all()
         if u.get("display_name", "").lower() == body.display_name.strip().lower()),
        None,
    )
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = user["id"]

    if _users_store.is_locked(user_id):
        locked_until = _users_store.locked_until_str(user_id)
        raise HTTPException(
            status_code=423,
            detail=f"Account locked until {locked_until}. Contact an admin to reset.",
        )

    if not _users_store.verify_password(user_id, body.password):
        # Re-check lockout in case this attempt triggered it
        if _users_store.is_locked(user_id):
            locked_until = _users_store.locked_until_str(user_id)
            raise HTTPException(
                status_code=423,
                detail=f"Account locked until {locked_until}. Contact an admin to reset.",
            )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _token_store.create(user_id)
    profile = _users_store.get(user_id)
    return {"token": token, "profile": _safe(profile)}


@router.post("/logout", status_code=204)
async def logout(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return
    token = authorization.removeprefix("Bearer ")
    if _token_store:
        _token_store.revoke(token)


@router.get("/me")
async def me(authorization: str | None = Header(default=None)):
    user_id = _require_token(authorization)
    if _users_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    profile = _users_store.get(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _safe(profile)


@router.get("/profiles")
async def profiles():
    """Public endpoint — profile list without sensitive fields, for login screen."""
    if _users_store is None:
        return []
    return _users_store.get_public()
