"""JWT access + refresh issuance, verification, and refresh rotation."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from social_agent.auth.refresh_store import RefreshTokenStore

ACCESS_TYP = "access"
REFRESH_TYP = "refresh"


class JwtAuthnError(RuntimeError):
    """Invalid, expired, or wrong-type JWT."""


class TokenReuseError(JwtAuthnError):
    """Refresh jti was missing (already rotated or revoked)."""


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    email: str | None
    exp: datetime


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"  # noqa: S105 — OAuth token_type, not a password

    def __repr__(self) -> str:
        # Never include raw tokens in logs/repr (issue #15).
        return (
            "TokenPair(access_token='***', refresh_token='***', "
            f"expires_in={self.expires_in!r}, token_type={self.token_type!r})"
        )


def _secret_from_env() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise JwtAuthnError("JWT_SECRET is required")
    if len(secret) < 32:
        raise JwtAuthnError("JWT_SECRET must be at least 32 characters")
    return secret


class JwtAuthn:
    """Issue/verify access JWTs and rotate refresh JWTs via a jti store."""

    def __init__(
        self,
        secret: str | None = None,
        *,
        refresh_store: RefreshTokenStore,
        access_ttl_seconds: int = 15 * 60,
        refresh_ttl_seconds: int = 60 * 60 * 24 * 7,
        algorithm: str = "HS256",
    ) -> None:
        self._secret = secret if secret is not None else _secret_from_env()
        if len(self._secret) < 32:
            raise JwtAuthnError("JWT secret must be at least 32 characters")
        if access_ttl_seconds <= 0 or refresh_ttl_seconds <= 0:
            raise ValueError("token TTLs must be positive")
        self._refresh_store = refresh_store
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds
        self._algorithm = algorithm

    def issue_pair(
        self,
        user_id: uuid.UUID,
        *,
        email: str | None = None,
    ) -> TokenPair:
        now = datetime.now(UTC)
        access = self._encode(
            {
                "typ": ACCESS_TYP,
                "sub": str(user_id),
                "email": email,
                "jti": str(uuid.uuid4()),
                "iat": now,
                "exp": now + timedelta(seconds=self._access_ttl),
            }
        )
        refresh_jti = str(uuid.uuid4())
        refresh = self._encode(
            {
                "typ": REFRESH_TYP,
                "sub": str(user_id),
                "email": email,
                "jti": refresh_jti,
                "iat": now,
                "exp": now + timedelta(seconds=self._refresh_ttl),
            }
        )
        self._refresh_store.save(refresh_jti, str(user_id), self._refresh_ttl)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self._access_ttl,
        )

    def verify_access(self, token: str) -> AccessClaims:
        payload = self._decode(token)
        if payload.get("typ") != ACCESS_TYP:
            raise JwtAuthnError("token is not an access token")
        try:
            user_id = uuid.UUID(str(payload["sub"]))
        except (KeyError, ValueError) as exc:
            raise JwtAuthnError("access token missing subject") from exc
        email = payload.get("email")
        if email is not None and not isinstance(email, str):
            raise JwtAuthnError("invalid email claim")
        exp_raw = payload.get("exp")
        if exp_raw is None:
            raise JwtAuthnError("access token missing exp")
        exp = datetime.fromtimestamp(int(exp_raw), tz=UTC)
        return AccessClaims(user_id=user_id, email=email, exp=exp)

    def rotate(self, refresh_token: str) -> TokenPair:
        payload = self._decode(refresh_token)
        if payload.get("typ") != REFRESH_TYP:
            raise JwtAuthnError("token is not a refresh token")
        jti = payload.get("jti")
        sub = payload.get("sub")
        if not isinstance(jti, str) or not isinstance(sub, str):
            raise JwtAuthnError("refresh token missing jti/sub")
        stored_user = self._refresh_store.pop(jti)
        if stored_user is None:
            raise TokenReuseError("refresh token reuse or unknown jti")
        if stored_user != sub:
            self._refresh_store.delete(jti)
            raise JwtAuthnError("refresh token subject mismatch")
        email = payload.get("email") if isinstance(payload.get("email"), str) else None
        return self.issue_pair(uuid.UUID(sub), email=email)

    def _encode(self, claims: dict[str, Any]) -> str:
        return jwt.encode(claims, self._secret, algorithm=self._algorithm)

    def _decode(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["exp", "sub", "typ"]},
            )
        except jwt.PyJWTError as exc:
            raise JwtAuthnError("invalid token") from exc
        if not isinstance(payload, dict):
            raise JwtAuthnError("invalid token payload")
        return payload
