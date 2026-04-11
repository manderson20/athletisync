from __future__ import annotations

import secrets
from typing import Any

from fastapi import HTTPException, Request, status
from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, submitted_token: str | None) -> None:
    expected = ensure_csrf_token(request)
    if not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def session_user_id(request: Request) -> int | None:
    raw_value: Any = request.session.get("user_id")
    return int(raw_value) if raw_value is not None else None
