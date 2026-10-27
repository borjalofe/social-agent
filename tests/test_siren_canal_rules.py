"""Siren canal-rules collection + per-channel item behind JWT."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.canal_rules import (
    EXPECTED_CANAL_RULES_COLLECTION_RELS,
    InMemoryCanalRuleStore,
    build_canal_rule_item,
    build_canal_rules_collection,
)
from social_agent.siren.home import SIREN_MEDIA_TYPE


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
def canal_rule_store() -> InMemoryCanalRuleStore:
    return InMemoryCanalRuleStore()


@pytest.fixture()
def client(authn: JwtAuthn, canal_rule_store: InMemoryCanalRuleStore) -> TestClient:
    return TestClient(create_app(authn=authn, canal_rule_store=canal_rule_store))


def test_build_canal_rules_collection_offers_add_action() -> None:
    user_id = uuid.uuid4()
    store = InMemoryCanalRuleStore()
    store.create(user_id, channel="linkedin", body="tono LI")
    entity = build_canal_rules_collection(user_id, store.list(user_id))
    assert entity["class"] == ["canal-rules", "collection"]
    assert len(entity["entities"]) == 1
    assert entity["entities"][0]["properties"]["channel"] == "linkedin"
    assert "actions" not in entity["entities"][0]
    assert entity["actions"][0]["name"] == "add-canal-rule"
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_CANAL_RULES_COLLECTION_RELS


def test_build_canal_rule_item_offers_update(
    canal_rule_store: InMemoryCanalRuleStore,
) -> None:
    user_id = uuid.uuid4()
    record = canal_rule_store.create(user_id, channel="x", body="corto")
    assert record is not None
    entity = build_canal_rule_item(record)
    assert entity["class"] == ["canal-rule", "item"]
    assert entity["actions"][0]["name"] == "update-canal-rule"
    assert entity["actions"][0]["href"] == "/canal-rules/x"


def test_canal_rules_requires_bearer(client: TestClient) -> None:
    assert client.get("/canal-rules").status_code == 401
    assert (
        client.post(
            "/canal-rules",
            json={"channel": "linkedin", "body": "x"},
        ).status_code
        == 401
    )


def test_canal_rules_create_get_update_and_duplicate(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    empty = client.get("/canal-rules", headers=headers)
    assert empty.status_code == 200
    assert empty.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    assert empty.json()["entities"] == []

    created = client.post(
        "/canal-rules",
        headers=headers,
        json={"channel": "linkedin", "body": "reglas LI"},
    )
    assert created.status_code == 200
    assert created.json()["properties"]["channel"] == "linkedin"
    assert created.json()["actions"][0]["name"] == "update-canal-rule"

    conflict = client.post(
        "/canal-rules",
        headers=headers,
        json={"channel": "linkedin", "body": "otra"},
    )
    assert conflict.status_code == 409

    got = client.get("/canal-rules/linkedin", headers=headers)
    assert got.status_code == 200
    assert got.json()["properties"]["body"] == "reglas LI"

    updated = client.put(
        "/canal-rules/linkedin",
        headers=headers,
        json={"body": "reglas LI v2"},
    )
    assert updated.status_code == 200
    assert updated.json()["properties"]["body"] == "reglas LI v2"

    listed = client.get("/canal-rules", headers=headers)
    assert len(listed.json()["entities"]) == 1


def test_canal_rules_item_not_found(client: TestClient, authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    assert client.get("/canal-rules/missing", headers=headers).status_code == 404
    assert (
        client.put(
            "/canal-rules/missing",
            headers=headers,
            json={"body": "x"},
        ).status_code
        == 404
    )


def test_canal_rules_isolated_per_user(client: TestClient, authn: JwtAuthn) -> None:
    pair_a = authn.issue_pair(uuid.uuid4())
    pair_b = authn.issue_pair(uuid.uuid4())
    client.post(
        "/canal-rules",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"channel": "linkedin", "body": "solo A"},
    )
    listed_b = client.get(
        "/canal-rules",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert listed_b.json()["entities"] == []
    assert (
        client.get(
            "/canal-rules/linkedin",
            headers={"Authorization": f"Bearer {pair_b.access_token}"},
        ).status_code
        == 404
    )
