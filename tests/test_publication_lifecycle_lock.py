"""Publication lifecycle lock: no edits once scheduled or published."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.publications import (
    InMemoryPublicationStore,
    build_publication_item,
    is_publication_locked,
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
def client(authn: JwtAuthn) -> TestClient:
    return TestClient(create_app(authn=authn, publication_store=InMemoryPublicationStore()))


@pytest.mark.parametrize(
    ("status", "locked"),
    [
        ("approved", False),
        ("scheduled", True),
        ("published", True),
    ],
)
def test_is_publication_locked(status: str, locked: bool) -> None:
    assert is_publication_locked(status) is locked


def test_build_item_omits_update_when_locked() -> None:
    user_id = uuid.uuid4()
    store = InMemoryPublicationStore()
    when = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    scheduled = store.create(
        user_id,
        channel="x",
        title=None,
        body="hola",
        status="scheduled",
        scheduled_at=when,
        published_at=None,
    )
    published = store.create(
        user_id,
        channel="x",
        title=None,
        body="listo",
        status="published",
        scheduled_at=None,
        published_at=when,
    )
    assert build_publication_item(scheduled)["actions"] == []
    assert build_publication_item(published)["actions"] == []


def test_build_item_offers_update_when_approved() -> None:
    user_id = uuid.uuid4()
    store = InMemoryPublicationStore()
    record = store.create(
        user_id,
        channel="linkedin",
        title="MVP",
        body="copy",
        status="approved",
        scheduled_at=None,
        published_at=None,
    )
    actions = build_publication_item(record)["actions"]
    assert len(actions) == 1
    assert actions[0]["name"] == "update-publication"


def test_put_rejected_when_scheduled_or_published(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    scheduled = client.post(
        "/publications",
        headers=headers,
        json={
            "channel": "linkedin",
            "body": "prog",
            "status": "scheduled",
            "scheduled_at": "2026-11-02T09:00:00+00:00",
        },
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["actions"] == []
    sched_id = scheduled.json()["properties"]["id"]
    locked = client.put(
        f"/publications/{sched_id}",
        headers=headers,
        json={"channel": "linkedin", "body": "nope", "status": "approved"},
    )
    assert locked.status_code == 409
    assert locked.json()["detail"] == "publication_locked"

    published = client.post(
        "/publications",
        headers=headers,
        json={
            "channel": "linkedin",
            "body": "out",
            "status": "published",
            "published_at": "2026-10-01T12:00:00+00:00",
        },
    )
    pub_id = published.json()["properties"]["id"]
    assert (
        client.put(
            f"/publications/{pub_id}",
            headers=headers,
            json={"channel": "linkedin", "body": "nope", "status": "approved"},
        ).status_code
        == 409
    )


def test_approved_can_transition_to_scheduled_then_locks(
    client: TestClient,
    authn: JwtAuthn,
) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    created = client.post(
        "/publications",
        headers=headers,
        json={"channel": "linkedin", "body": "draft-final", "status": "approved"},
    )
    pub_id = created.json()["properties"]["id"]
    assert created.json()["actions"][0]["name"] == "update-publication"

    scheduled = client.put(
        f"/publications/{pub_id}",
        headers=headers,
        json={
            "channel": "linkedin",
            "body": "draft-final",
            "status": "scheduled",
            "scheduled_at": "2026-11-02T09:00:00+00:00",
        },
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["actions"] == []
    assert (
        client.put(
            f"/publications/{pub_id}",
            headers=headers,
            json={"channel": "linkedin", "body": "changed", "status": "approved"},
        ).status_code
        == 409
    )
