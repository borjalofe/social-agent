"""Siren social-accounts: sealed credentials, never leaked in responses."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.crypto import generate_key, unseal
from social_agent.siren.home import SIREN_MEDIA_TYPE
from social_agent.siren.social_accounts import (
    EXPECTED_SOCIAL_ACCOUNTS_COLLECTION_RELS,
    InMemorySocialAccountStore,
    build_social_account_item,
    build_social_accounts_collection,
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
def social_account_store() -> InMemorySocialAccountStore:
    return InMemorySocialAccountStore()


@pytest.fixture()
def client(
    authn: JwtAuthn,
    social_account_store: InMemorySocialAccountStore,
) -> TestClient:
    return TestClient(
        create_app(
            authn=authn,
            social_account_store=social_account_store,
            fernet_key=_TEST_FERNET_KEY,
        )
    )


def test_build_social_accounts_collection_hides_secrets() -> None:
    user_id = uuid.uuid4()
    store = InMemorySocialAccountStore()
    store.create(
        user_id,
        channel="linkedin",
        handle="@me",
        credentials_encrypted="cipher-should-not-appear",
    )
    entity = build_social_accounts_collection(user_id, store.list(user_id))
    assert entity["class"] == ["social-accounts", "collection"]
    assert entity["actions"][0]["name"] == "add-social-account"
    props = entity["entities"][0]["properties"]
    assert props["handle"] == "@me"
    assert props["credentials_set"] is True
    assert "credentials" not in props
    assert "credentials_encrypted" not in props
    assert "cipher-should-not-appear" not in str(entity)
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_SOCIAL_ACCOUNTS_COLLECTION_RELS


def test_build_social_account_item_hides_secrets(
    social_account_store: InMemorySocialAccountStore,
) -> None:
    user_id = uuid.uuid4()
    record = social_account_store.create(
        user_id,
        channel="x",
        handle="@x",
        credentials_encrypted="sealed-blob",
    )
    assert record is not None
    entity = build_social_account_item(record)
    assert entity["properties"]["credentials_set"] is True
    assert "credentials_encrypted" not in entity["properties"]
    assert "sealed-blob" not in str(entity)
    assert entity["actions"][0]["href"] == "/social-accounts/x"


def test_social_accounts_requires_bearer(client: TestClient) -> None:
    assert client.get("/social-accounts").status_code == 401
    assert (
        client.post(
            "/social-accounts",
            json={
                "channel": "linkedin",
                "handle": "@a",
                "credentials": "tok",
            },
        ).status_code
        == 401
    )


def test_social_accounts_create_get_update_seals_credentials(
    client: TestClient,
    authn: JwtAuthn,
    social_account_store: InMemorySocialAccountStore,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    secret = "oauth-token-plaintext"

    created = client.post(
        "/social-accounts",
        headers=headers,
        json={
            "channel": "linkedin",
            "handle": "@alice",
            "credentials": secret,
        },
    )
    assert created.status_code == 200
    assert created.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    body = created.json()
    assert body["properties"]["handle"] == "@alice"
    assert body["properties"]["credentials_set"] is True
    assert secret not in created.text
    assert "credentials_encrypted" not in body["properties"]

    stored = social_account_store.get(user_id, "linkedin")
    assert stored is not None
    assert stored.credentials_encrypted != secret
    assert unseal(stored.credentials_encrypted, key=_TEST_FERNET_KEY) == secret

    conflict = client.post(
        "/social-accounts",
        headers=headers,
        json={
            "channel": "linkedin",
            "handle": "@alice2",
            "credentials": "other",
        },
    )
    assert conflict.status_code == 409

    updated = client.put(
        "/social-accounts/linkedin",
        headers=headers,
        json={"handle": "@alice-new", "credentials": "rotated"},
    )
    assert updated.status_code == 200
    assert updated.json()["properties"]["handle"] == "@alice-new"
    assert "rotated" not in updated.text
    stored2 = social_account_store.get(user_id, "linkedin")
    assert stored2 is not None
    assert unseal(stored2.credentials_encrypted, key=_TEST_FERNET_KEY) == "rotated"


def test_social_accounts_isolated_per_user(client: TestClient, authn: JwtAuthn) -> None:
    pair_a = authn.issue_pair(uuid.uuid4())
    pair_b = authn.issue_pair(uuid.uuid4())
    client.post(
        "/social-accounts",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"channel": "linkedin", "handle": "@a", "credentials": "secret-a"},
    )
    listed_b = client.get(
        "/social-accounts",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert listed_b.json()["entities"] == []
    assert (
        client.get(
            "/social-accounts/linkedin",
            headers={"Authorization": f"Bearer {pair_b.access_token}"},
        ).status_code
        == 404
    )
