"""Auth HTTP endpoints for Radio-TTY.

GET  /auth/setup-status            — returns whether first-run setup is needed
POST /auth/setup                   — create the initial admin account (first-run only)
POST /auth/login                   — verify credentials, issue session token
POST /auth/logout                  — revoke session token
GET  /auth/me                      — return current user profile (sensitive fields stripped)
GET  /auth/profiles                — public list of profiles for the login screen
GET  /auth/ws-ticket               — issue a one-time, 60s WS connection ticket
POST /auth/admin/revoke-user/{id}  — (admin) revoke all sessions for a user
GET  /auth/admin/audit             — (admin) tail the audit log

These are mounted under /auth by server.py after startup.
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from backend.auth_ratelimit import LoginRateLimiter, get_client_ip
from backend.persistence.users import SENSITIVE_PROFILE_FIELDS

router = APIRouter()

# Populated by server.py via init() after singletons are ready.
_users_store       = None
_token_store       = None
_config            = None
_audit_log         = None
_disconnect_user   = None   # async callable: disconnect_user(user_id: str) -> None

_rate_limiter = LoginRateLimiter()


def init(users_store, token_store, config=None, audit_log=None, disconnect_user_fn=None) -> None:
    global _users_store, _token_store, _config, _audit_log, _disconnect_user
    _users_store     = users_store
    _token_store     = token_store
    _config          = config
    _audit_log       = audit_log
    _disconnect_user = disconnect_user_fn
    _rate_limiter.reset()  # clear any accumulated state from previous runs / tests


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


def _require_admin(authorization: str | None) -> str:
    """Like _require_token but also asserts is_admin; returns user_id."""
    user_id = _require_token(authorization)
    if _users_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    profile = _users_store.get(user_id)
    if not profile or not profile.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


def _safe(u: dict) -> dict:
    return {k: v for k, v in u.items() if k not in SENSITIVE_PROFILE_FIELDS}


def _audit(event: str, *, user_id: str = "", ip: str = "", detail: str = "") -> None:
    if _audit_log is not None:
        _audit_log.log(event, user_id=user_id, ip=ip, detail=detail)


@router.get("/setup-status")
async def setup_status():
    """Returns whether first-run admin setup is still needed."""
    if _users_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    return {"setup_needed": _users_store.is_empty()}


class SetupRequest(BaseModel):
    display_name: str
    password: str
    avatar_emoji: str = "👤"
    operator_name: str = ""
    callsign: str = ""
    location: str = ""


@router.post("/setup")
async def setup(body: SetupRequest, request: Request):
    """First-run only: create the initial admin account and return a session token."""
    if _users_store is None or _token_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    if not _users_store.is_empty():
        raise HTTPException(status_code=409, detail="Setup already complete")

    ip = get_client_ip(request)
    allowed, retry_after = _rate_limiter.check(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts — try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    display_name = body.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Display name is required")
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    user = _users_store.create(
        display_name=display_name,
        password=body.password,
        avatar_emoji=body.avatar_emoji,
        operator_name=body.operator_name.strip() or display_name,
        callsign=body.callsign.strip().upper(),
        location=body.location.strip(),
        is_admin=True,
    )

    if _config is not None:
        if body.callsign.strip():
            _config["callsign"] = body.callsign.strip().upper()
        if body.location.strip():
            _config["location"] = body.location.strip()
        _config.save()

    token = _token_store.create(user["id"])
    _audit("login_success", user_id=user["id"], ip=ip, detail="initial_setup")
    return {"token": token, "profile": _safe(user)}


class LoginRequest(BaseModel):
    display_name: str
    password: str


@router.post("/login")
async def login(body: LoginRequest, request: Request):
    if _users_store is None or _token_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")

    ip = get_client_ip(request)
    allowed, retry_after = _rate_limiter.check(ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many attempts — try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    user = next(
        (u for u in _users_store.get_all()
         if u.get("display_name", "").lower() == body.display_name.strip().lower()),
        None,
    )
    if user is None:
        _audit("login_fail", ip=ip, detail=f"unknown_user:{body.display_name.strip()!r}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = user["id"]

    if _users_store.is_locked(user_id):
        locked_until = _users_store.locked_until_str(user_id)
        _audit("login_lockout", user_id=user_id, ip=ip)
        raise HTTPException(
            status_code=423,
            detail=f"Account locked until {locked_until}. Contact an admin to reset.",
        )

    if not _users_store.verify_password(user_id, body.password):
        if _users_store.is_locked(user_id):
            locked_until = _users_store.locked_until_str(user_id)
            _audit("login_lockout", user_id=user_id, ip=ip)
            raise HTTPException(
                status_code=423,
                detail=f"Account locked until {locked_until}. Contact an admin to reset.",
            )
        _audit("login_fail", user_id=user_id, ip=ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = _token_store.create(user_id)
    profile = _users_store.get(user_id)
    _audit("login_success", user_id=user_id, ip=ip)
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


@router.get("/ws-ticket")
async def ws_ticket(authorization: str | None = Header(default=None)):
    """Issue a single-use, 60-second WS connection ticket.

    The client uses this ticket in the WS URL (?ticket=...) instead of the
    long-lived session token, keeping the reusable token out of server logs.
    """
    if _token_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")
    user_id = _require_token(authorization)
    ticket = _token_store.create_ticket(user_id)
    return {"ticket": ticket}


@router.post("/admin/revoke-user/{target_user_id}", status_code=200)
async def admin_revoke_user(
    target_user_id: str,
    authorization: str | None = Header(default=None),
):
    """(Admin) Revoke all active sessions for *target_user_id* and force-disconnect."""
    if _token_store is None or _users_store is None:
        raise HTTPException(status_code=503, detail="Server not ready")

    admin_id = _require_admin(authorization)

    if not _users_store.get(target_user_id):
        raise HTTPException(status_code=404, detail="User not found")

    count = _token_store.revoke_all_for_user(target_user_id)
    _audit("token_revoked", user_id=target_user_id, detail=f"revoked_by:{admin_id} count:{count}")

    if _disconnect_user is not None:
        await _disconnect_user(target_user_id)

    return {"revoked": count}


@router.get("/admin/audit")
async def admin_audit(
    limit: int = 200,
    authorization: str | None = Header(default=None),
):
    """(Admin) Return the last *limit* audit log entries."""
    _require_admin(authorization)
    if _audit_log is None:
        raise HTTPException(status_code=503, detail="Audit log not available")
    return _audit_log.tail(min(limit, 1000))
