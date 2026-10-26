"""Redis cache for agent session payloads (keyed by agent_sessions.id)."""

from __future__ import annotations

import json
import os
import uuid
from typing import Any, Protocol

KEY_PREFIX = "agent_session:"
DEFAULT_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 days


class RedisLike(Protocol):
    def set(self, name: str, value: str, ex: int | None = None) -> Any: ...

    def get(self, name: str) -> str | None: ...

    def delete(self, *names: str) -> int: ...


def session_key(session_id: uuid.UUID) -> str:
    return f"{KEY_PREFIX}{session_id}"


def redis_from_url(url: str | None = None) -> Any:
    """Build a Redis client from REDIS_URL (or the given URL)."""
    import redis

    resolved = url or os.environ.get("REDIS_URL")
    if not resolved:
        raise RuntimeError("REDIS_URL is required (e.g. redis://127.0.0.1:6379/0)")
    return redis.Redis.from_url(resolved, decode_responses=True)


class AgentSessionPayloadStore:
    """Put/get/delete JSON payloads for agent sessions."""

    def __init__(
        self,
        redis_client: RedisLike,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds

    def put(
        self,
        session_id: uuid.UUID,
        payload: dict[str, Any],
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        ttl = self._ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            raise ValueError("ttl_seconds must be positive")
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        self._redis.set(session_key(session_id), body, ex=ttl)

    def get(self, session_id: uuid.UUID) -> dict[str, Any] | None:
        raw = self._redis.get(session_key(session_id))
        if raw is None:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise TypeError("session payload must be a JSON object")
        return data

    def delete(self, session_id: uuid.UUID) -> bool:
        return self._redis.delete(session_key(session_id)) > 0
