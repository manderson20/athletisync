from __future__ import annotations

import base64
import hashlib
import secrets
from typing import Any

from fastapi import HTTPException, Request, status
from cryptography.fernet import Fernet, InvalidToken
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


def encrypt_secret(value: str, key_material: str) -> str:
    if not value:
        return ""
    token = _secret_fernet(key_material).encrypt(value.encode("utf-8")).decode("utf-8")
    return f"enc:{token}"


def decrypt_secret(value: str | None, key_material: str) -> str | None:
    if not value:
        return None
    if not value.startswith("enc:"):
        return value
    token = value[4:]
    try:
        return _secret_fernet(key_material).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored Google OAuth secret could not be decrypted with the current APP_SECRET_KEY.") from exc


def _secret_fernet(key_material: str) -> Fernet:
    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))
