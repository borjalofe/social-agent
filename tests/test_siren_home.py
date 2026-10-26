"""Siren home resource: entry entity + catalog links behind JWT."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.home import EXPECTED_HOME_RELS, SIREN_MEDIA_TYPE, build_home


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


def test_build_home_is_siren_entry_with_catalog_links() -> None:
    user_id = uuid.uuid4()
    entity = build_home(user_id)
    assert entity["class"] == ["home"]
    assert entity["properties"]["user_id"] == str(user_id)
    assert entity["actions"] == []
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_HOME_RELS
    self_link = next(link for link in entity["links"] if link["rel"] == ["self"])
    assert self_link["href"] == "/"


def test_home_requires_bearer(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 401


def test_home_rejects_invalid_bearer(client: TestClient) -> None:
    response = client.get("/", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401


def test_home_returns_siren_for_valid_access_token(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id, email="home@example.com")
    response = client.get(
        "/",
        headers={"Authorization": f"Bearer {pair.access_token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    body = response.json()
    assert body["class"] == ["home"]
    assert body["properties"]["user_id"] == str(user_id)
    assert body["properties"]["email"] == "home@example.com"
    rels = {tuple(link["rel"]) for link in body["links"]}
    assert rels == EXPECTED_HOME_RELS
    assert body["actions"] == []
