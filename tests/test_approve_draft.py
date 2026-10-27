"""Approve agent-run draft → persist approved publication."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.agent_run import (
    InMemoryAgentRunPayloadStore,
    InMemoryAgentRunStore,
    build_agent_run_item,
)
from social_agent.siren.approve_draft import ApproveDraftError, approve_draft
from social_agent.siren.publications import InMemoryPublicationStore


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
def agent_run_store() -> InMemoryAgentRunStore:
    return InMemoryAgentRunStore()


@pytest.fixture()
def payload_store() -> InMemoryAgentRunPayloadStore:
    return InMemoryAgentRunPayloadStore()


@pytest.fixture()
def publication_store() -> InMemoryPublicationStore:
    return InMemoryPublicationStore()


@pytest.fixture()
def client(
    authn: JwtAuthn,
    agent_run_store: InMemoryAgentRunStore,
    payload_store: InMemoryAgentRunPayloadStore,
    publication_store: InMemoryPublicationStore,
) -> TestClient:
    return TestClient(
        create_app(
            authn=authn,
            agent_run_store=agent_run_store,
            agent_run_payload_store=payload_store,
            publication_store=publication_store,
        )
    )


def test_build_item_offers_approve_when_draft_present(
    agent_run_store: InMemoryAgentRunStore,
) -> None:
    user_id = uuid.uuid4()
    record = agent_run_store.create(
        user_id,
        agent_name="copy_linkedin",
        channel="linkedin",
        status="waiting_approval",
    )
    entity = build_agent_run_item(
        record,
        payload={"draft": {"body": "hola LI", "title": "Hook"}},
    )
    assert entity["actions"][0]["name"] == "approve-draft"
    assert entity["actions"][0]["href"] == f"/agent-run/{record.id}/approve"


def test_build_item_omits_approve_without_draft(
    agent_run_store: InMemoryAgentRunStore,
) -> None:
    user_id = uuid.uuid4()
    record = agent_run_store.create(
        user_id,
        agent_name="copy_linkedin",
        channel="linkedin",
    )
    assert build_agent_run_item(record, payload={"turns": []})["actions"] == []


def test_approve_draft_persists_publication(
    agent_run_store: InMemoryAgentRunStore,
    payload_store: InMemoryAgentRunPayloadStore,
    publication_store: InMemoryPublicationStore,
) -> None:
    user_id = uuid.uuid4()
    record = agent_run_store.create(
        user_id,
        agent_name="copy_linkedin",
        channel="linkedin",
    )
    payload_store.put(
        record.id,
        {
            "agent_name": "copy_linkedin",
            "channel": "linkedin",
            "draft": {"body": "copy final", "title": "MVP"},
            "turns": [],
        },
    )
    run, pub, next_payload = approve_draft(
        user_id,
        record.id,
        agent_run_store=agent_run_store,
        payload_store=payload_store,
        publication_store=publication_store,
    )
    assert run.status == "completed"
    assert pub.status == "approved"
    assert pub.channel == "linkedin"
    assert pub.body == "copy final"
    assert pub.title == "MVP"
    assert next_payload["publication_id"] == str(pub.id)
    assert publication_store.get(user_id, pub.id) is not None


def test_approve_draft_requires_draft(
    agent_run_store: InMemoryAgentRunStore,
    payload_store: InMemoryAgentRunPayloadStore,
    publication_store: InMemoryPublicationStore,
) -> None:
    user_id = uuid.uuid4()
    record = agent_run_store.create(
        user_id,
        agent_name="copy_linkedin",
        channel="linkedin",
    )
    payload_store.put(record.id, {"turns": []})
    with pytest.raises(ApproveDraftError) as exc:
        approve_draft(
            user_id,
            record.id,
            agent_run_store=agent_run_store,
            payload_store=payload_store,
            publication_store=publication_store,
        )
    assert exc.value.code == "draft_missing"


def test_approve_http_creates_publication_and_completes_run(
    client: TestClient,
    authn: JwtAuthn,
    agent_run_store: InMemoryAgentRunStore,
    payload_store: InMemoryAgentRunPayloadStore,
    publication_store: InMemoryPublicationStore,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    record = agent_run_store.create(
        user_id,
        agent_name="copy_linkedin",
        channel="linkedin",
        status="waiting_approval",
    )
    payload_store.put(record.id, {"draft": "post body", "channel": "linkedin"})

    response = client.post(f"/agent-run/{record.id}/approve", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["class"] == ["publication", "item"]
    assert body["properties"]["status"] == "approved"
    assert body["properties"]["body"] == "post body"
    pub_id = uuid.UUID(body["properties"]["id"])
    assert publication_store.get(user_id, pub_id) is not None
    assert agent_run_store.get(user_id, record.id).status == "completed"

    listed = client.get("/publications", headers=headers)
    assert len(listed.json()["entities"]) == 1

    # Second approve is blocked
    again = client.post(f"/agent-run/{record.id}/approve", headers=headers)
    assert again.status_code == 409
    assert again.json()["detail"] == "not_approvable"


def test_approve_requires_bearer(client: TestClient) -> None:
    assert client.post(f"/agent-run/{uuid.uuid4()}/approve").status_code == 401


def test_approve_isolated_per_user(
    client: TestClient,
    authn: JwtAuthn,
    agent_run_store: InMemoryAgentRunStore,
    payload_store: InMemoryAgentRunPayloadStore,
) -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    record = agent_run_store.create(
        owner,
        agent_name="copy_linkedin",
        channel="linkedin",
    )
    payload_store.put(record.id, {"draft": "solo owner"})
    pair_other = authn.issue_pair(other)
    assert (
        client.post(
            f"/agent-run/{record.id}/approve",
            headers={"Authorization": f"Bearer {pair_other.access_token}"},
        ).status_code
        == 404
    )
