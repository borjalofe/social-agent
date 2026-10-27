"""Siren publications collection + item behind JWT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.home import SIREN_MEDIA_TYPE
from social_agent.siren.publications import (
    EXPECTED_PUBLICATIONS_COLLECTION_RELS,
    InMemoryPublicationStore,
    build_publication_item,
    build_publications_collection,
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


@pytest.fixture()
def publication_store() -> InMemoryPublicationStore:
    return InMemoryPublicationStore()


@pytest.fixture()
def client(authn: JwtAuthn, publication_store: InMemoryPublicationStore) -> TestClient:
    return TestClient(create_app(authn=authn, publication_store=publication_store))


def test_build_publications_collection_offers_add() -> None:
    user_id = uuid.uuid4()
    store = InMemoryPublicationStore()
    store.create(
        user_id,
        channel="linkedin",
        title="Post",
        body="body",
        status="approved",
        scheduled_at=None,
        published_at=None,
    )
    entity = build_publications_collection(user_id, store.list(user_id))
    assert entity["class"] == ["publications", "collection"]
    assert entity["actions"][0]["name"] == "add-publication"
    assert len(entity["entities"]) == 1
    assert "actions" not in entity["entities"][0]
    assert "body" not in entity["entities"][0]["properties"]
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_PUBLICATIONS_COLLECTION_RELS


def test_build_publication_item_offers_update_when_approved(
    publication_store: InMemoryPublicationStore,
) -> None:
    user_id = uuid.uuid4()
    when = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    record = publication_store.create(
        user_id,
        channel="x",
        title=None,
        body="hola",
        status="approved",
        scheduled_at=when,
        published_at=None,
    )
    entity = build_publication_item(record)
    assert entity["class"] == ["publication", "item"]
    assert entity["properties"]["status"] == "approved"
    assert entity["properties"]["scheduled_at"] == when.isoformat()
    assert entity["actions"][0]["name"] == "update-publication"
    assert entity["actions"][0]["href"] == f"/publications/{record.id}"


def test_publications_requires_bearer(client: TestClient) -> None:
    assert client.get("/publications").status_code == 401
    assert (
        client.post(
            "/publications",
            json={"channel": "linkedin", "body": "x"},
        ).status_code
        == 401
    )


def test_publications_create_list_get_update(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    empty = client.get("/publications", headers=headers)
    assert empty.status_code == 200
    assert empty.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    assert empty.json()["entities"] == []

    created = client.post(
        "/publications",
        headers=headers,
        json={
            "channel": "linkedin",
            "title": "MVP",
            "body": "copy final",
            "status": "approved",
        },
    )
    assert created.status_code == 200
    item = created.json()
    assert item["class"] == ["publication", "item"]
    pub_id = item["properties"]["id"]
    assert item["properties"]["body"] == "copy final"
    assert item["properties"]["status"] == "approved"

    listed = client.get("/publications", headers=headers)
    assert len(listed.json()["entities"]) == 1
    assert listed.json()["entities"][0]["properties"]["id"] == pub_id

    got = client.get(f"/publications/{pub_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["properties"]["title"] == "MVP"

    updated = client.put(
        f"/publications/{pub_id}",
        headers=headers,
        json={
            "channel": "linkedin",
            "title": "MVP",
            "body": "copy final v2",
            "status": "scheduled",
            "scheduled_at": "2026-11-02T09:00:00+00:00",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["properties"]["body"] == "copy final v2"
    assert updated.json()["properties"]["status"] == "scheduled"
    assert updated.json()["properties"]["scheduled_at"] == "2026-11-02T09:00:00+00:00"


def test_publications_rejects_invalid_status(client: TestClient, authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    response = client.post(
        "/publications",
        headers=headers,
        json={"channel": "linkedin", "body": "x", "status": "draft"},
    )
    assert response.status_code == 422


def test_publications_item_not_found(client: TestClient, authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    missing = uuid.uuid4()
    assert client.get(f"/publications/{missing}", headers=headers).status_code == 404


def test_publications_isolated_per_user(client: TestClient, authn: JwtAuthn) -> None:
    pair_a = authn.issue_pair(uuid.uuid4())
    pair_b = authn.issue_pair(uuid.uuid4())
    created = client.post(
        "/publications",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"channel": "linkedin", "body": "solo A"},
    )
    pub_id = created.json()["properties"]["id"]
    listed_b = client.get(
        "/publications",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert listed_b.json()["entities"] == []
    assert (
        client.get(
            f"/publications/{pub_id}",
            headers={"Authorization": f"Bearer {pair_b.access_token}"},
        ).status_code
        == 404
    )
