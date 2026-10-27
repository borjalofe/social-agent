"""Siren llm-connections: sealed credentials, never leaked in responses."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.crypto import generate_key, unseal
from social_agent.siren.home import SIREN_MEDIA_TYPE
from social_agent.siren.llm_connections import (
    EXPECTED_LLM_CONNECTIONS_COLLECTION_RELS,
    InMemoryLlmConnectionStore,
    build_llm_connection_item,
    build_llm_connections_collection,
)

_TEST_FERNET_KEY = generate_key().decode()


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
def llm_connection_store() -> InMemoryLlmConnectionStore:
    return InMemoryLlmConnectionStore()


@pytest.fixture()
def client(
    authn: JwtAuthn,
    llm_connection_store: InMemoryLlmConnectionStore,
) -> TestClient:
    return TestClient(
        create_app(
            authn=authn,
            llm_connection_store=llm_connection_store,
            fernet_key=_TEST_FERNET_KEY,
        )
    )


def test_build_llm_connections_collection_hides_secrets() -> None:
    user_id = uuid.uuid4()
    store = InMemoryLlmConnectionStore()
    store.create(
        user_id,
        provider="anthropic",
        label="default",
        credentials_encrypted="cipher-should-not-appear",
    )
    entity = build_llm_connections_collection(user_id, store.list(user_id))
    assert entity["class"] == ["llm-connections", "collection"]
    assert entity["actions"][0]["name"] == "add-llm-connection"
    props = entity["entities"][0]["properties"]
    assert props["provider"] == "anthropic"
    assert props["label"] == "default"
    assert props["credentials_set"] is True
    assert "credentials" not in props
    assert "credentials_encrypted" not in props
    assert "cipher-should-not-appear" not in str(entity)
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_LLM_CONNECTIONS_COLLECTION_RELS


def test_build_llm_connection_item_hides_secrets(
    llm_connection_store: InMemoryLlmConnectionStore,
) -> None:
    user_id = uuid.uuid4()
    record = llm_connection_store.create(
        user_id,
        provider="openai",
        label="work",
        credentials_encrypted="sealed-blob",
    )
    assert record is not None
    entity = build_llm_connection_item(record)
    assert entity["properties"]["credentials_set"] is True
    assert "credentials_encrypted" not in entity["properties"]
    assert "sealed-blob" not in str(entity)
    assert entity["actions"][0]["href"] == "/llm-connections/openai"


def test_llm_connections_requires_bearer(client: TestClient) -> None:
    assert client.get("/llm-connections").status_code == 401
    assert (
        client.post(
            "/llm-connections",
            json={
                "provider": "anthropic",
                "label": "default",
                "credentials": "sk-ant",
            },
        ).status_code
        == 401
    )


def test_llm_connections_create_get_update_seals_credentials(
    client: TestClient,
    authn: JwtAuthn,
    llm_connection_store: InMemoryLlmConnectionStore,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    secret = "sk-ant-plaintext"

    created = client.post(
        "/llm-connections",
        headers=headers,
        json={
            "provider": "anthropic",
            "label": "default",
            "credentials": secret,
        },
    )
    assert created.status_code == 200
    assert created.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    body = created.json()
    assert body["properties"]["label"] == "default"
    assert body["properties"]["credentials_set"] is True
    assert secret not in created.text
    assert "credentials_encrypted" not in body["properties"]

    stored = llm_connection_store.get(user_id, "anthropic")
    assert stored is not None
    assert stored.credentials_encrypted != secret
    assert unseal(stored.credentials_encrypted, key=_TEST_FERNET_KEY) == secret

    conflict = client.post(
        "/llm-connections",
        headers=headers,
        json={
            "provider": "anthropic",
            "label": "other",
            "credentials": "other",
        },
    )
    assert conflict.status_code == 409

    updated = client.put(
        "/llm-connections/anthropic",
        headers=headers,
        json={"label": "prod", "credentials": "rotated-key"},
    )
    assert updated.status_code == 200
    assert updated.json()["properties"]["label"] == "prod"
    assert "rotated-key" not in updated.text
    stored2 = llm_connection_store.get(user_id, "anthropic")
    assert stored2 is not None
    assert unseal(stored2.credentials_encrypted, key=_TEST_FERNET_KEY) == "rotated-key"


def test_llm_connections_isolated_per_user(client: TestClient, authn: JwtAuthn) -> None:
    pair_a = authn.issue_pair(uuid.uuid4())
    pair_b = authn.issue_pair(uuid.uuid4())
    client.post(
        "/llm-connections",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"provider": "anthropic", "label": "a", "credentials": "secret-a"},
    )
    listed_b = client.get(
        "/llm-connections",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert listed_b.json()["entities"] == []
    assert (
        client.get(
            "/llm-connections/anthropic",
            headers={"Authorization": f"Bearer {pair_b.access_token}"},
        ).status_code
        == 404
    )
