"""Siren voice resource: GET/PUT body behind JWT with update-voice action."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.home import SIREN_MEDIA_TYPE
from social_agent.siren.voice import EXPECTED_VOICE_RELS, InMemoryVoiceStore, build_voice


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
def voice_store() -> InMemoryVoiceStore:
    return InMemoryVoiceStore()


@pytest.fixture()
def client(authn: JwtAuthn, voice_store: InMemoryVoiceStore) -> TestClient:
    return TestClient(create_app(authn=authn, voice_store=voice_store))


def test_build_voice_offers_update_action() -> None:
    user_id = uuid.uuid4()
    entity = build_voice(user_id, body="tono directo")
    assert entity["class"] == ["voice"]
    assert entity["properties"]["user_id"] == str(user_id)
    assert entity["properties"]["body"] == "tono directo"
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_VOICE_RELS
    assert entity["actions"][0]["name"] == "update-voice"
    assert entity["actions"][0]["method"] == "PUT"
    assert entity["actions"][0]["href"] == "/voice"


def test_voice_requires_bearer(client: TestClient) -> None:
    assert client.get("/voice").status_code == 401
    assert client.put("/voice", json={"body": "x"}).status_code == 401


def test_voice_get_empty_then_put_persists(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id, email="v@example.com")
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    empty = client.get("/voice", headers=headers)
    assert empty.status_code == 200
    assert empty.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    assert empty.json()["properties"]["body"] == ""
    assert empty.json()["actions"][0]["name"] == "update-voice"

    updated = client.put("/voice", headers=headers, json={"body": "voz empírica"})
    assert updated.status_code == 200
    assert updated.json()["properties"]["body"] == "voz empírica"
    assert updated.json()["class"] == ["voice"]

    again = client.get("/voice", headers=headers)
    assert again.json()["properties"]["body"] == "voz empírica"


def test_voice_put_isolated_per_user(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    pair_a = authn.issue_pair(a)
    pair_b = authn.issue_pair(b)
    client.put(
        "/voice",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"body": "solo A"},
    )
    got_b = client.get(
        "/voice",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert got_b.json()["properties"]["body"] == ""
