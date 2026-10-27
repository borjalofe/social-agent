"""Siren agent-run: start session, list/get with payload, isolation."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.siren.agent_run import (
    EXPECTED_AGENT_RUN_COLLECTION_RELS,
    InMemoryAgentRunPayloadStore,
    InMemoryAgentRunStore,
    build_agent_run_collection,
    build_agent_run_item,
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
def agent_run_store() -> InMemoryAgentRunStore:
    return InMemoryAgentRunStore()


@pytest.fixture()
def agent_run_payload_store() -> InMemoryAgentRunPayloadStore:
    return InMemoryAgentRunPayloadStore()


@pytest.fixture()
def client(
    authn: JwtAuthn,
    agent_run_store: InMemoryAgentRunStore,
    agent_run_payload_store: InMemoryAgentRunPayloadStore,
) -> TestClient:
    return TestClient(
        create_app(
            authn=authn,
            agent_run_store=agent_run_store,
            agent_run_payload_store=agent_run_payload_store,
        )
    )


def test_build_agent_run_collection_offers_start() -> None:
    user_id = uuid.uuid4()
    store = InMemoryAgentRunStore()
    store.create(user_id, agent_name="copy_linkedin", channel="linkedin")
    entity = build_agent_run_collection(user_id, store.list(user_id))
    assert entity["class"] == ["agent-run", "collection"]
    assert entity["actions"][0]["name"] == "start-agent-run"
    assert "payload" not in entity["entities"][0]["properties"]
    rels = {tuple(link["rel"]) for link in entity["links"]}
    assert rels == EXPECTED_AGENT_RUN_COLLECTION_RELS


def test_build_agent_run_item_includes_payload(
    agent_run_store: InMemoryAgentRunStore,
) -> None:
    user_id = uuid.uuid4()
    record = agent_run_store.create(
        user_id,
        agent_name="copy_linkedin",
        channel="linkedin",
    )
    entity = build_agent_run_item(record, payload={"input": "tema", "turns": []})
    assert entity["class"] == ["agent-run", "item"]
    assert entity["properties"]["payload"]["input"] == "tema"
    assert entity["actions"] == []


def test_agent_run_requires_bearer(client: TestClient) -> None:
    assert client.get("/agent-run").status_code == 401
    assert (
        client.post(
            "/agent-run",
            json={"agent_name": "copy_linkedin", "input": "x"},
        ).status_code
        == 401
    )


def test_agent_run_start_list_get(
    client: TestClient,
    authn: JwtAuthn,
    agent_run_payload_store: InMemoryAgentRunPayloadStore,
) -> None:
    user_id = uuid.uuid4()
    pair = authn.issue_pair(user_id)
    headers = {"Authorization": f"Bearer {pair.access_token}"}

    empty = client.get("/agent-run", headers=headers)
    assert empty.status_code == 200
    assert empty.headers["content-type"].startswith(SIREN_MEDIA_TYPE)
    assert empty.json()["entities"] == []
    assert empty.json()["actions"][0]["name"] == "start-agent-run"

    started = client.post(
        "/agent-run",
        headers=headers,
        json={
            "agent_name": "copy_linkedin",
            "channel": "linkedin",
            "input": "lanzar MVP",
        },
    )
    assert started.status_code == 200
    item = started.json()
    assert item["class"] == ["agent-run", "item"]
    run_id = item["properties"]["id"]
    assert item["properties"]["status"] == "open"
    assert item["properties"]["agent_name"] == "copy_linkedin"
    assert item["properties"]["payload"]["input"] == "lanzar MVP"
    assert item["properties"]["payload"]["turns"] == []

    stored = agent_run_payload_store.get(uuid.UUID(run_id))
    assert stored is not None
    assert stored["input"] == "lanzar MVP"

    listed = client.get("/agent-run", headers=headers)
    assert len(listed.json()["entities"]) == 1
    assert "payload" not in listed.json()["entities"][0]["properties"]

    got = client.get(f"/agent-run/{run_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["properties"]["payload"]["input"] == "lanzar MVP"


def test_agent_run_item_not_found(client: TestClient, authn: JwtAuthn) -> None:
    pair = authn.issue_pair(uuid.uuid4())
    headers = {"Authorization": f"Bearer {pair.access_token}"}
    assert client.get(f"/agent-run/{uuid.uuid4()}", headers=headers).status_code == 404


def test_agent_run_isolated_per_user(client: TestClient, authn: JwtAuthn) -> None:
    pair_a = authn.issue_pair(uuid.uuid4())
    pair_b = authn.issue_pair(uuid.uuid4())
    started = client.post(
        "/agent-run",
        headers={"Authorization": f"Bearer {pair_a.access_token}"},
        json={"agent_name": "copy_linkedin", "input": "solo A"},
    )
    run_id = started.json()["properties"]["id"]
    listed_b = client.get(
        "/agent-run",
        headers={"Authorization": f"Bearer {pair_b.access_token}"},
    )
    assert listed_b.json()["entities"] == []
    assert (
        client.get(
            f"/agent-run/{run_id}",
            headers={"Authorization": f"Bearer {pair_b.access_token}"},
        ).status_code
        == 404
    )
