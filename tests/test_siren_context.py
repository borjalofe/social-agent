"""Siren context collection + item resources behind JWT."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.context import (
    EXPECTED_CONTEXT_COLLECTION_RELS,
    InMemoryContextStore,
    build_context_collection,
    build_context_item,
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
def context_store() -> InMemoryContextStore:
    return InMemoryContextStore()


@pytest.fixture()
def client(authn: JwtAuthn, context_store: InMemoryContextStore) -> TestClient:
    return TestClient(create_app(authn=authn, context_store=context_store))


def test_build_context_collection_offers_add_action() -> None:
    user_id = uuid.uuid4()
    store = InMemoryContextStore()
    store.create(user_id, title="A", body="uno")
    entity = build_context_collection(user_id, store.list(user_id))
    assert entity["class"] == ["context", "collection"]
    assert entity["properties"]["user_id"] == str(user_id)
    assert len(entity["entities"]) == 1
    assert entity["entities"][0]["rel"] == ["item"]
    assert "actions" not in entity["entities"][0]
    assert entity["actions"][0]["name"] == "add-context"
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_CONTEXT_COLLECTION_RELS


def test_build_context_item_offers_update_action(context_store: InMemoryContextStore) -> None:
    user_id = uuid.uuid4()
    record = context_store.create(user_id, title="T", body="B")
    entity = build_context_item(record)
    assert entity["class"] == ["context", "item"]
    assert entity["properties"]["title"] == "T"
    assert entity["actions"][0]["name"] == "update-context"
    assert entity["actions"][0]["href"] == f"/context/{record.id}"


def test_context_requires_bearer(client: TestClient) -> None:
    assert client.get("/context").status_code == 401
    assert client.post("/context", json={"title": "t", "body": "b"}).status_code == 401


def test_context_collection_create_get_update(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    empty = client.get("/context", headers=headers)
    assert empty.status_code == 200
    assert empty.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    assert empty.json()["entities"] == []
    assert empty.json()["actions"][0]["name"] == "add-context"

    created = client.post(
        "/context",
        headers=headers,
        json={"title": "Producto", "body": "contexto A"},
    )
    assert created.status_code == 200
    item = created.json()
    assert item["class"] == ["context", "item"]
    doc_id = item["properties"]["id"]
    assert item["properties"]["body"] == "contexto A"
    assert item["actions"][0]["name"] == "update-context"

    listed = client.get("/context", headers=headers)
    assert len(listed.json()["entities"]) == 1
    assert listed.json()["entities"][0]["properties"]["id"] == doc_id

    got = client.get(f"/context/{doc_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["properties"]["title"] == "Producto"

    updated = client.put(
        f"/context/{doc_id}",
        headers=headers,
        json={"title": "Producto", "body": "contexto B"},
    )
    assert updated.status_code == 200
    assert updated.json()["properties"]["body"] == "contexto B"


def test_context_item_not_found(client: TestClient, authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    missing = uuid.uuid4()
    assert client.get(f"/context/{missing}", headers=headers).status_code == 404
    assert (
        client.put(
            f"/context/{missing}",
            headers=headers,
            json={"title": "x", "body": "y"},
        ).status_code
        == 404
    )


def test_context_isolated_per_user(client: TestClient, authn: JwtAuthn) -> None:
    a = uuid.uuid4()
    b = uuid.uuid4()
    pair_a = authn.issue_pair(a)
    pair_b = authn.issue_pair(b)
    created = client.post(
        "/context",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"title": "solo A", "body": "secret"},
    )
    doc_id = created.json()["properties"]["id"]

    listed_b = client.get(
        "/context",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert listed_b.json()["entities"] == []
    assert (
        client.get(
            f"/context/{doc_id}",
            headers={"Authorization": f"Bearer {pair_b.access_token}"},
        ).status_code
        == 404
    )
