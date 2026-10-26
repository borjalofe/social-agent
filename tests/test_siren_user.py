"""Siren user resource: profile entity behind JWT."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.home import SIREN_MEDIA_TYPE
from social_agent.siren.user import EXPECTED_USER_RELS, build_user


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


@pytest.fixture()
def client(authn: JwtAuthn) -> TestClient:
    return TestClient(create_app(authn=authn))


def test_build_user_is_siren_profile() -> None:
    user_id = uuid.uuid4()
    entity = build_user(user_id, email="u@example.com")
    assert entity["class"] == ["user"]
    assert entity["properties"]["user_id"] == str(user_id)
    assert entity["properties"]["email"] == "u@example.com"
    assert "password_hash" not in entity["properties"]
    assert entity["actions"] == []
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_USER_RELS
    self_link = next(link for link in entity["links"] if link["rel"] == ["self"])
    assert self_link["href"] == "/user"


def test_user_requires_bearer(client: TestClient) -> None:
    response = client.get("/user")
    assert response.status_code == 401


def test_user_rejects_invalid_bearer(client: TestClient) -> None:
    response = client.get("/user", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_user_returns_siren_for_valid_access_token(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id, email="user@example.com")
    response = client.get(
        "/user",
        headers={"Authorization": f"Bearer {pair.access_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    body = response.json()
    assert body["class"] == ["user"]
    assert body["properties"]["user_id"] == str(user_id)
    assert body["properties"]["email"] == "user@example.com"
    assert "password_hash" not in body["properties"]
    rels = {tuple(link["rel"]) for link in body["links"]}
    assert rels == EXPECTED_USER_RELS
    assert body["actions"] == []
