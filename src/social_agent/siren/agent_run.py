"""Siren `agent-run` collection + item (session metadata + Redis-shaped payload)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

_COLLECTION_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/agent-run"),
    ("home", "/"),
)

EXPECTED_AGENT_RUN_COLLECTION_RELS: frozenset[tuple[str, ...]] = frozenset(
    ((rel,) for rel, _href in _COLLECTION_LINKS)
)

START_AGENT_RUN_ACTION: dict[str, Any] = {
    "name": "start-agent-run",
    "method": "POST",
    "href": "/agent-run",
    "type": "application/json",
    "fields": [
        {"name": "agent_name", "type": "text"},
        {"name": "channel", "type": "text"},
        {"name": "input", "type": "text"},
    ],
}

APPROVE_DRAFT_ACTION: dict[str, Any] = {
    "name": "approve-draft",
    "method": "POST",
    "href": "",  # filled per item
    "type": "application/json",
    "fields": [],
}


@dataclass(frozen=True)
class AgentRunRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    agent_name: str
    channel: str | None
    status: str


class AgentRunStore(Protocol):
    def list(self, user_id: uuid.UUID) -> list[AgentRunRecord]: ...

    def get(self, user_id: uuid.UUID, run_id: uuid.UUID) -> AgentRunRecord | None: ...

    def create(
        self,
        user_id: uuid.UUID,
        *,
        agent_name: str,
        channel: str | None,
        status: str = "open",
    ) -> AgentRunRecord: ...

    def update_status(
        self,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        status: str,
    ) -> AgentRunRecord | None: ...


class AgentRunPayloadStore(Protocol):
    def put(self, session_id: uuid.UUID, payload: dict[str, Any]) -> None: ...

    def get(self, session_id: uuid.UUID) -> dict[str, Any] | None: ...


class InMemoryAgentRunStore:
    """Process-local agent-run metadata (inject durable store for production)."""

    def __init__(self) -> None:
        self._runs: dict[uuid.UUID, AgentRunRecord] = {}

    def list(self, user_id: uuid.UUID) -> list[AgentRunRecord]:
        return [run for run in self._runs.values() if run.user_id == user_id]

    def get(self, user_id: uuid.UUID, run_id: uuid.UUID) -> AgentRunRecord | None:
        run = self._runs.get(run_id)
        if run is None or run.user_id != user_id:
            return None
        return run

    def create(
        self,
        user_id: uuid.UUID,
        *,
        agent_name: str,
        channel: str | None,
        status: str = "open",
    ) -> AgentRunRecord:
        record = AgentRunRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            agent_name=agent_name,
            channel=channel,
            status=status,
        )
        self._runs[record.id] = record
        return record

    def update_status(
        self,
        user_id: uuid.UUID,
        run_id: uuid.UUID,
        *,
        status: str,
    ) -> AgentRunRecord | None:
        existing = self.get(user_id, run_id)
        if existing is None:
            return None
        record = AgentRunRecord(
            id=existing.id,
            user_id=existing.user_id,
            agent_name=existing.agent_name,
            channel=existing.channel,
            status=status,
        )
        self._runs[run_id] = record
        return record


class InMemoryAgentRunPayloadStore:
    """Process-local payloads (swap for AgentSessionPayloadStore + Redis)."""

    def __init__(self) -> None:
        self._payloads: dict[uuid.UUID, dict[str, Any]] = {}

    def put(self, session_id: uuid.UUID, payload: dict[str, Any]) -> None:
        self._payloads[session_id] = dict(payload)

    def get(self, session_id: uuid.UUID) -> dict[str, Any] | None:
        data = self._payloads.get(session_id)
        return None if data is None else dict(data)


def _item_href(run_id: uuid.UUID) -> str:
    return f"/agent-run/{run_id}"


def _meta_properties(record: AgentRunRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "user_id": str(record.user_id),
        "agent_name": record.agent_name,
        "channel": record.channel,
        "status": record.status,
    }


def _payload_has_draft(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    raw = payload.get("draft")
    if isinstance(raw, str):
        return bool(raw.strip())
    if isinstance(raw, dict):
        body = raw.get("body")
        return isinstance(body, str) and bool(body.strip())
    return False


def build_agent_run_item(
    record: AgentRunRecord,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a Siren agent-run item; payload is conversation/draft JSON (not secrets)."""
    properties = _meta_properties(record)
    properties["payload"] = payload if payload is not None else {}
    actions: list[dict[str, Any]] = []
    if record.status in {"open", "waiting_approval"} and _payload_has_draft(payload):
        actions.append(
            {
                **APPROVE_DRAFT_ACTION,
                "href": f"{_item_href(record.id)}/approve",
            }
        )
    return {
        "class": ["agent-run", "item"],
        "properties": properties,
        "entities": [],
        "links": [
            {"rel": ["self"], "href": _item_href(record.id)},
            {"rel": ["collection"], "href": "/agent-run"},
            {"rel": ["home"], "href": "/"},
        ],
        "actions": actions,
    }


def build_agent_run_collection(
    user_id: uuid.UUID,
    items: list[AgentRunRecord],
) -> dict[str, Any]:
    """Build a Siren agent-run collection; list entities omit payload."""
    entities: list[dict[str, Any]] = []
    for record in items:
        href = _item_href(record.id)
        entities.append(
            {
                "class": ["agent-run", "item"],
                "rel": ["item"],
                "href": href,
                "properties": {
                    "id": str(record.id),
                    "agent_name": record.agent_name,
                    "channel": record.channel,
                    "status": record.status,
                },
                "links": [{"rel": ["self"], "href": href}],
            }
        )
    return {
        "class": ["agent-run", "collection"],
        "properties": {"user_id": str(user_id)},
        "entities": entities,
        "links": [{"rel": [rel], "href": href} for rel, href in _COLLECTION_LINKS],
        "actions": [dict(START_AGENT_RUN_ACTION)],
    }
