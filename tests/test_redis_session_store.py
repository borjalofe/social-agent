"""Agent session payload store (Redis)."""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest

from social_agent.sessions.redis_store import (
    DEFAULT_TTL_SECONDS,
    KEY_PREFIX,
    AgentSessionPayloadStore,
    session_key,
)


class _FakeRedis:
    """Minimal Redis stand-in for unit tests (no network)."""

    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self.data[name] = value
        if ex is not None:
            self.ttls[name] = ex
        return True

    def get(self, name: str) -> str | None:
        return self.data.get(name)

    def delete(self, *names: str) -> int:
        removed = 0
        for name in names:
            if name in self.data:
                del self.data[name]
                self.ttls.pop(name, None)
                removed += 1
        return removed


@pytest.fixture()
def store() -> AgentSessionPayloadStore:
    return AgentSessionPayloadStore(_FakeRedis())


def test_session_key_uses_prefix_and_uuid() -> None:
    session_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert session_key(session_id) == f"{KEY_PREFIX}{session_id}"


def test_put_get_roundtrip_json_payload(store: AgentSessionPayloadStore) -> None:
    session_id = uuid.uuid4()
    payload = {"draft": "Hello LI", "turns": [{"role": "user", "text": "hi"}]}
    store.put(session_id, payload)
    assert store.get(session_id) == payload


def test_put_sets_ttl(store: AgentSessionPayloadStore) -> None:
    session_id = uuid.uuid4()
    store.put(session_id, {"a": 1}, ttl_seconds=120)
    key = session_key(session_id)
    assert store._redis.ttls[key] == 120  # type: ignore[attr-defined]


def test_get_missing_returns_none(store: AgentSessionPayloadStore) -> None:
    assert store.get(uuid.uuid4()) is None


def test_delete_removes_payload(store: AgentSessionPayloadStore) -> None:
    session_id = uuid.uuid4()
    store.put(session_id, {"x": 1})
    assert store.delete(session_id) is True
    assert store.get(session_id) is None
    assert store.delete(session_id) is False


def test_default_ttl_constant() -> None:
    assert DEFAULT_TTL_SECONDS == 60 * 60 * 24 * 7


@pytest.fixture(scope="module")
def redis_url() -> str:
    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL not set (Redis required for integration tests)")
    return url


def test_live_redis_put_get_delete(redis_url: str) -> None:
    import redis

    client: Any = redis.Redis.from_url(redis_url, decode_responses=True)
    client.ping()
    store = AgentSessionPayloadStore(client, ttl_seconds=60)
    session_id = uuid.uuid4()
    try:
        store.put(session_id, {"live": True, "n": 2})
        assert store.get(session_id) == {"live": True, "n": 2}
        assert store.delete(session_id) is True
        assert store.get(session_id) is None
    finally:
        store.delete(session_id)
        client.close()
