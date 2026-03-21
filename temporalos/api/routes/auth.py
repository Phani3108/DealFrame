"""Auth API routes — register, login, refresh, profile."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from ...auth import (
    check_rate_limit, get_current_user, login, refresh_token, register, require_auth,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/register")
async def register_user(req: RegisterRequest) -> dict:
    """Register a new user account."""
    try:
        result = register(req.email, req.password, req.display_name)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login_user(req: LoginRequest) -> dict:
    """Authenticate and get tokens."""
    try:
        result = login(req.email, req.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/refresh")
async def refresh(req: RefreshRequest) -> dict:
    """Refresh an access token."""
    try:
        result = refresh_token(req.refresh_token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
async def get_profile(user: dict = Depends(require_auth)) -> dict:
    """Get current user profile."""
    return user
