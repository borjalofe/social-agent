"""Server-side refresh token jti store (required for rotation / reuse detection)."""

from __future__ import annotations

from typing import Any, Protocol


class RefreshTokenStore(Protocol):
    def save(self, jti: str, user_id: str, ttl_seconds: int) -> None: ...

    def pop(self, jti: str) -> str | None:
        """Return user_id for jti and remove it, or None if unknown/expired."""

    def delete(self, jti: str) -> None: ...


class RedisRefreshTokenStore:
    """Stores active refresh jtis in Redis: `refresh_jti:{jti}` → user_id."""

    KEY_PREFIX = "refresh_jti:"

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    def _key(self, jti: str) -> str:
        return f"{self.KEY_PREFIX}{jti}"

    def save(self, jti: str, user_id: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._redis.set(self._key(jti), user_id, ex=ttl_seconds)

    def pop(self, jti: str) -> str | None:
        key = self._key(jti)
        # GETDEL when available; fallback for older Redis.
        getdel = getattr(self._redis, "getdel", None)
        if callable(getdel):
            value = getdel(key)
            return str(value) if value is not None else None
        value = self._redis.get(key)
        if value is None:
            return None
        self._redis.delete(key)
        return str(value)

    def delete(self, jti: str) -> None:
        self._redis.delete(self._key(jti))
