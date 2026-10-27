"""Siren `llm-connections` collection + item (one sealed set per user+provider)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

_COLLECTION_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/llm-connections"),
    ("home", "/"),
)

EXPECTED_LLM_CONNECTIONS_COLLECTION_RELS: frozenset[tuple[str, ...]] = frozenset(
    ((rel,) for rel, _href in _COLLECTION_LINKS)
)

ADD_LLM_CONNECTION_ACTION: dict[str, Any] = {
    "name": "add-llm-connection",
    "method": "POST",
    "href": "/llm-connections",
    "type": "application/json",
    "fields": [
        {"name": "provider", "type": "text"},
        {"name": "label", "type": "text"},
        {"name": "credentials", "type": "text"},
    ],
}

UPDATE_LLM_CONNECTION_ACTION: dict[str, Any] = {
    "name": "update-llm-connection",
    "method": "PUT",
    "href": "",  # filled per item
    "type": "application/json",
    "fields": [
        {"name": "label", "type": "text"},
        {"name": "credentials", "type": "text"},
    ],
}


@dataclass(frozen=True)
class LlmConnectionRecord:
    user_id: uuid.UUID
    provider: str
    label: str
    credentials_encrypted: str


class LlmConnectionStore(Protocol):
    def list(self, user_id: uuid.UUID) -> list[LlmConnectionRecord]: ...

    def get(self, user_id: uuid.UUID, provider: str) -> LlmConnectionRecord | None: ...

    def create(
        self,
        user_id: uuid.UUID,
        *,
        provider: str,
        label: str,
        credentials_encrypted: str,
    ) -> LlmConnectionRecord | None:
        """Return the new record, or None if (user_id, provider) already exists."""

    def update(
        self,
        user_id: uuid.UUID,
        provider: str,
        *,
        label: str,
        credentials_encrypted: str,
    ) -> LlmConnectionRecord | None:
        """Return the updated record, or None if missing for this user."""


class InMemoryLlmConnectionStore:
    """Process-local LLM connections (inject a durable store for production)."""

    def __init__(self) -> None:
        self._connections: dict[tuple[uuid.UUID, str], LlmConnectionRecord] = {}

    def list(self, user_id: uuid.UUID) -> list[LlmConnectionRecord]:
        return [row for (uid, _), row in self._connections.items() if uid == user_id]

    def get(self, user_id: uuid.UUID, provider: str) -> LlmConnectionRecord | None:
        return self._connections.get((user_id, provider))

    def create(
        self,
        user_id: uuid.UUID,
        *,
        provider: str,
        label: str,
        credentials_encrypted: str,
    ) -> LlmConnectionRecord | None:
        key = (user_id, provider)
        if key in self._connections:
            return None
        record = LlmConnectionRecord(
            user_id=user_id,
            provider=provider,
            label=label,
            credentials_encrypted=credentials_encrypted,
        )
        self._connections[key] = record
        return record

    def update(
        self,
        user_id: uuid.UUID,
        provider: str,
        *,
        label: str,
        credentials_encrypted: str,
    ) -> LlmConnectionRecord | None:
        key = (user_id, provider)
        if key not in self._connections:
            return None
        record = LlmConnectionRecord(
            user_id=user_id,
            provider=provider,
            label=label,
            credentials_encrypted=credentials_encrypted,
        )
        self._connections[key] = record
        return record


def _item_href(provider: str) -> str:
    return f"/llm-connections/{provider}"


def _public_properties(record: LlmConnectionRecord) -> dict[str, Any]:
    # Never expose plaintext or ciphertext credentials in Siren bodies (DEC-002).
    return {
        "user_id": str(record.user_id),
        "provider": record.provider,
        "label": record.label,
        "credentials_set": bool(record.credentials_encrypted),
    }


def build_llm_connection_item(record: LlmConnectionRecord) -> dict[str, Any]:
    """Build a Siren llm-connection item (no credential material)."""
    href = _item_href(record.provider)
    action = {**UPDATE_LLM_CONNECTION_ACTION, "href": href}
    return {
        "class": ["llm-connection", "item"],
        "properties": _public_properties(record),
        "entities": [],
        "links": [
            {"rel": ["self"], "href": href},
            {"rel": ["collection"], "href": "/llm-connections"},
            {"rel": ["home"], "href": "/"},
        ],
        "actions": [action],
    }


def build_llm_connections_collection(
    user_id: uuid.UUID,
    items: list[LlmConnectionRecord],
) -> dict[str, Any]:
    """Build a Siren llm-connections collection; items link to detail (no nested actions)."""
    entities: list[dict[str, Any]] = []
    for record in items:
        href = _item_href(record.provider)
        entities.append(
            {
                "class": ["llm-connection", "item"],
                "rel": ["item"],
                "href": href,
                "properties": {
                    "provider": record.provider,
                    "label": record.label,
                    "credentials_set": bool(record.credentials_encrypted),
                },
                "links": [{"rel": ["self"], "href": href}],
            }
        )
    return {
        "class": ["llm-connections", "collection"],
        "properties": {"user_id": str(user_id)},
        "entities": entities,
        "links": [{"rel": [rel], "href": href} for rel, href in _COLLECTION_LINKS],
        "actions": [dict(ADD_LLM_CONNECTION_ACTION)],
    }
