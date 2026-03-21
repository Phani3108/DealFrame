"""Authentication system — JWT auth, API keys, rate limiting.

Provides register/login/refresh with bcrypt password hashing.
API key auth for SDK access. Rate limiting per tier.
DB persistence for users via optional session_factory.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# JWT — use AUTH_SECRET env var for stable signing across restarts
_SECRET_KEY = os.environ.get("AUTH_SECRET", "") or secrets.token_hex(32)
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60
_REFRESH_TOKEN_EXPIRE_DAYS = 30

_security = HTTPBearer(auto_error=False)

# In-memory user store (populated from DB at startup when available)
_users: Dict[str, Dict[str, Any]] = {}
_api_keys: Dict[str, str] = {}  # api_key → email
_rate_limits: Dict[str, list] = {}  # email → [timestamps]
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None

TIER_LIMITS = {
    "free": {"videos_per_month": 3, "requests_per_minute": 10},
    "pro": {"videos_per_month": 100, "requests_per_minute": 60},
    "enterprise": {"videos_per_month": 10000, "requests_per_minute": 300},
}


def _hash_password(password: str) -> str:
    """Hash password with salt using hashlib (no bcrypt dependency)."""
    salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}:{hashed.hex()}"


def _verify_password(password: str, hashed: str) -> bool:
    """Verify password against stored hash."""
    try:
        salt, hash_hex = hashed.split(":", 1)
        expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(expected.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def _create_token(payload: Dict[str, Any], expires_delta: timedelta) -> str:
    """Create a simple JWT-like token using HMAC-SHA256."""
    import base64
    import json

    exp = datetime.now(timezone.utc) + expires_delta
    payload["exp"] = exp.isoformat()
    payload["iat"] = datetime.now(timezone.utc).isoformat()

    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=")
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    signature_input = header + b"." + body
    sig = hmac.new(_SECRET_KEY.encode(), signature_input, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(sig).rstrip(b"=")

    return (header + b"." + body + b"." + signature).decode()


def _decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a JWT-like token."""
    import base64
    import json

    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b, body_b, sig_b = parts
        signature_input = (header_b + "." + body_b).encode()
        expected_sig = hmac.new(_SECRET_KEY.encode(), signature_input, hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(sig_b + "==")

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload = json.loads(base64.urlsafe_b64decode(body_b + "=="))
        exp = datetime.fromisoformat(payload.get("exp", "2000-01-01T00:00:00+00:00"))
        if exp < datetime.now(timezone.utc):
            return None

        return payload
    except Exception:
        return None


def register(email: str, password: str, display_name: str = "",
             role: str = "analyst", tier: str = "free") -> Dict[str, Any]:
    """Register a new user. Returns user info + tokens."""
    if email in _users:
        raise ValueError("Email already registered")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    api_key = f"tos_{secrets.token_hex(24)}"
    _users[email] = {
        "email": email,
        "display_name": display_name or email.split("@")[0],
        "hashed_password": _hash_password(password),
        "role": role,
        "tier": tier,
        "api_key": api_key,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _api_keys[api_key] = email

    access = _create_token(
        {"sub": email, "role": role, "tier": tier},
        timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh = _create_token(
        {"sub": email, "type": "refresh"},
        timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return {
        "email": email,
        "display_name": _users[email]["display_name"],
        "role": role,
        "tier": tier,
        "api_key": api_key,
        "access_token": access,
        "refresh_token": refresh,
    }


def login(email: str, password: str) -> Dict[str, Any]:
    """Authenticate a user. Returns tokens."""
    user = _users.get(email)
    if not user or not _verify_password(password, user["hashed_password"]):
        raise ValueError("Invalid email or password")

    access = _create_token(
        {"sub": email, "role": user["role"], "tier": user.get("tier", "free")},
        timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh = _create_token(
        {"sub": email, "type": "refresh"},
        timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS),
    )

    return {
        "email": email,
        "display_name": user["display_name"],
        "role": user["role"],
        "access_token": access,
        "refresh_token": refresh,
    }


def refresh_token(token: str) -> Dict[str, Any]:
    """Refresh an access token using a refresh token."""
    payload = _decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise ValueError("Invalid refresh token")

    email = payload["sub"]
    user = _users.get(email)
    if not user:
        raise ValueError("User not found")

    access = _create_token(
        {"sub": email, "role": user["role"], "tier": user.get("tier", "free")},
        timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access}


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
    request: Request = None,
) -> Optional[Dict[str, Any]]:
    """FastAPI dependency — extract user from JWT or API key."""
    # Try Bearer token
    if credentials and credentials.credentials:
        payload = _decode_token(credentials.credentials)
        if payload:
            email = payload.get("sub")
            user = _users.get(email)
            if user:
                return {
                    "email": email,
                    "role": user["role"],
                    "tier": user.get("tier", "free"),
                    "display_name": user["display_name"],
                }

    # Try API key header
    if request:
        api_key = request.headers.get("X-API-Key", "")
        if api_key and api_key in _api_keys:
            email = _api_keys[api_key]
            user = _users.get(email)
            if user:
                return {
                    "email": email,
                    "role": user["role"],
                    "tier": user.get("tier", "free"),
                    "display_name": user["display_name"],
                }

    return None


def require_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_security),
    request: Request = None,
) -> Dict[str, Any]:
    """FastAPI dependency — require authenticated user."""
    user = get_current_user(credentials, request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory — require specific role(s)."""
    def _check(user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return _check


def check_rate_limit(email: str, tier: str = "free") -> bool:
    """Check if user is within rate limits. Returns True if allowed."""
    now = time.time()
    window = 60  # 1 minute window
    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"])["requests_per_minute"]

    if email not in _rate_limits:
        _rate_limits[email] = []

    # Clean old entries
    _rate_limits[email] = [t for t in _rate_limits[email] if now - t < window]

    if len(_rate_limits[email]) >= limit:
        return False

    _rate_limits[email].append(now)
    return True


# ── DB persistence helpers ────────────────────────────────────────────────────

def init_auth(session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
              secret_key: str = "") -> None:
    """Initialize auth with DB persistence and stable secret key."""
    global _session_factory, _SECRET_KEY
    _session_factory = session_factory
    if secret_key:
        _SECRET_KEY = secret_key


async def persist_user(email: str) -> None:
    """Persist a user record to DB after registration."""
    if not _session_factory:
        return
    user = _users.get(email)
    if not user:
        return
    from .._db_lazy import get_user_model
    UserModel = get_user_model()
    async with _session_factory() as session:
        existing = (await session.execute(
            select(UserModel).where(UserModel.email == email)
        )).scalar_one_or_none()
        if not existing:
            session.add(UserModel(
                email=email,
                display_name=user.get("display_name", ""),
                hashed_password=user.get("hashed_password", ""),
                role=user.get("role", "analyst"),
                tier=user.get("tier", "free"),
                api_key=user.get("api_key", ""),
            ))
            await session.commit()


async def load_users_from_db() -> None:
    """Load users from DB into memory at startup."""
    if not _session_factory:
        return
    from .._db_lazy import get_user_model
    UserModel = get_user_model()
    async with _session_factory() as session:
        rows = (await session.execute(select(UserModel))).scalars().all()
        for r in rows:
            email = r.email
            _users[email] = {
                "email": email,
                "display_name": r.display_name or email.split("@")[0],
                "hashed_password": r.hashed_password or "",
                "role": r.role or "analyst",
                "tier": r.tier or "free",
                "api_key": r.api_key or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            if r.api_key:
                _api_keys[r.api_key] = email
