"""JWT access + refresh with rotation; tokens must not appear in repr."""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest

from social_agent.auth.jwt_authn import (
    AccessClaims,
    JwtAuthn,
    JwtAuthnError,
    TokenReuseError,
)


class _FakeRefreshStore:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def save(self, jti: str, user_id: str, ttl_seconds: int) -> None:
        assert ttl_seconds > 0
        self.data[jti] = user_id

    def pop(self, jti: str) -> str | None:
        return self.data.pop(jti, None)

    def delete(self, jti: str) -> None:
        self.data.pop(jti, None)


@pytest.fixture()
def authn() -> JwtAuthn:
    return JwtAuthn(
        secret="test-secret-at-least-32-bytes-long!!",
        refresh_store=_FakeRefreshStore(),
        access_ttl_seconds=60,
        refresh_ttl_seconds=3600,
    )


def test_issue_pair_and_verify_access(authn: JwtAuthn) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id, email="a@example.com")
    assert pair.token_type == "bearer"
    assert pair.expires_in == 60
    claims = authn.verify_access(pair.access_token)
    assert isinstance(claims, AccessClaims)
    assert claims.user_id == user_id
    assert claims.email == "a@example.com"


def test_access_token_rejected_as_refresh_subject(authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    with pytest.raises(JwtAuthnError):
        authn.rotate(pair.access_token)


def test_refresh_token_rejected_as_access(authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    with pytest.raises(JwtAuthnError):
        authn.verify_access(pair.refresh_token)


def test_rotate_issues_new_pair_and_invalidates_old_refresh(authn: JwtAuthn) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id, email="b@example.com")
    rotated = authn.rotate(pair.refresh_token)
    assert rotated.access_token != pair.access_token
    assert rotated.refresh_token != pair.refresh_token
    claims = authn.verify_access(rotated.access_token)
    assert claims.user_id == user_id
    with pytest.raises(TokenReuseError):
        authn.rotate(pair.refresh_token)


def test_token_pair_repr_redacts_secrets(authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    text = repr(pair)
    assert pair.access_token not in text
    assert pair.refresh_token not in text
    assert "***" in text


def test_expired_access_rejected() -> None:
    authn = JwtAuthn(
        secret="test-secret-at-least-32-bytes-long!!",
        refresh_store=_FakeRefreshStore(),
        access_ttl_seconds=1,
        refresh_ttl_seconds=60,
    )
    pair = authn.issue_pair(uuid.uuid4())
    time.sleep(1.1)
    with pytest.raises(JwtAuthnError):
        authn.verify_access(pair.access_token)


def test_wrong_secret_rejected(authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    other = JwtAuthn(
        secret="other-secret-at-least-32-bytes-long!",
        refresh_store=_FakeRefreshStore(),
    )
    with pytest.raises(JwtAuthnError):
        other.verify_access(pair.access_token)


def test_live_redis_refresh_store_roundtrip() -> None:
    import os

    import redis

    url = os.environ.get("REDIS_URL")
    if not url:
        pytest.skip("REDIS_URL not set")
    client: Any = redis.Redis.from_url(url, decode_responses=True)
    from social_agent.auth.refresh_store import RedisRefreshTokenStore

    store = RedisRefreshTokenStore(client)
    authn = JwtAuthn(
        secret="test-secret-at-least-32-bytes-long!!",
        refresh_store=store,
        access_ttl_seconds=60,
        refresh_ttl_seconds=120,
    )
    user_id = uuid.uuid4()
    try:
        pair = authn.issue_pair(user_id)
        rotated = authn.rotate(pair.refresh_token)
        assert authn.verify_access(rotated.access_token).user_id == user_id
        with pytest.raises(TokenReuseError):
            authn.rotate(pair.refresh_token)
    finally:
        client.close()
