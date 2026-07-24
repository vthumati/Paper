"""Password hashing (stdlib scrypt, no native deps) and JWT helpers.

The HLD specifies OIDC/SSO + OTP for production (FR-A-3); this is the
MVP email+password shim that the same RBAC/token layer sits on top of.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return f"scrypt${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, salt_b64, dk_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(dk_b64)
        dk = hashlib.scrypt(
            password.encode(), salt=salt, n=_SCRYPT["n"], r=_SCRYPT["r"],
            p=_SCRYPT["p"], dklen=len(expected),
        )
        return hmac.compare_digest(dk, expected)
    except Exception:
        return False


def create_access_token(subject: str, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "tv": token_version,  # must match the user's current token_version
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str | None:
    """Return the subject (user id) for a structurally valid, unexpired token."""
    payload = decode_token_payload(token)
    return payload.get("sub") if payload else None


def decode_token_payload(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
