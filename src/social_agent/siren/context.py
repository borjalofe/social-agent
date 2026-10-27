"""Siren `context` collection + item resources (many docs per user)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

_COLLECTION_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/context"),
    ("home", "/"),
)

EXPECTED_CONTEXT_COLLECTION_RELS: frozenset[tuple[str, ...]] = frozenset(
    ((rel,) for rel, _href in _COLLECTION_LINKS)
)

ADD_CONTEXT_ACTION: dict[str, Any] = {
    "name": "add-context",
    "method": "POST",
    "href": "/context",
    "type": "application/json",
    "fields": [
        {"name": "title", "type": "text"},
        {"name": "body", "type": "text"},
    ],
}

UPDATE_CONTEXT_ACTION: dict[str, Any] = {
    "name": "update-context",
    "method": "PUT",
    "href": "",  # filled per item
    "type": "application/json",
    "fields": [
        {"name": "title", "type": "text"},
        {"name": "body", "type": "text"},
    ],
}


@dataclass(frozen=True)
class ContextRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    body: str


class ContextStore(Protocol):
    def list(self, user_id: uuid.UUID) -> list[ContextRecord]: ...

    def get(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> ContextRecord | None: ...

    def create(self, user_id: uuid.UUID, *, title: str, body: str) -> ContextRecord: ...

    def update(
        self,
        user_id: uuid.UUID,
        doc_id: uuid.UUID,
        *,
        title: str,
        body: str,
    ) -> ContextRecord | None: ...


class InMemoryContextStore:
    """Process-local context docs (inject a durable store for production)."""

    def __init__(self) -> None:
        self._docs: dict[uuid.UUID, ContextRecord] = {}

    def list(self, user_id: uuid.UUID) -> list[ContextRecord]:
        return [doc for doc in self._docs.values() if doc.user_id == user_id]

    def get(self, user_id: uuid.UUID, doc_id: uuid.UUID) -> ContextRecord | None:
        doc = self._docs.get(doc_id)
        if doc is None or doc.user_id != user_id:
            return None
        return doc

    def create(self, user_id: uuid.UUID, *, title: str, body: str) -> ContextRecord:
        record = ContextRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            title=title,
            body=body,
        )
        self._docs[record.id] = record
        return record

    def update(
        self,
        user_id: uuid.UUID,
        doc_id: uuid.UUID,
        *,
        title: str,
        body: str,
    ) -> ContextRecord | None:
        existing = self.get(user_id, doc_id)
        if existing is None:
            return None
        record = ContextRecord(
            id=doc_id,
            user_id=user_id,
            title=title,
            body=body,
        )
        self._docs[doc_id] = record
        return record


def _item_href(doc_id: uuid.UUID) -> str:
    return f"/context/{doc_id}"


def build_context_item(record: ContextRecord) -> dict[str, Any]:
    """Build a Siren context item entity with update-context action."""
    href = _item_href(record.id)
    action = {**UPDATE_CONTEXT_ACTION, "href": href}
    return {
        "class": ["context", "item"],
        "properties": {
            "id": str(record.id),
            "user_id": str(record.user_id),
            "title": record.title,
            "body": record.body,
        },
        "entities": [],
        "links": [
            {"rel": ["self"], "href": href},
            {"rel": ["collection"], "href": "/context"},
            {"rel": ["home"], "href": "/"},
        ],
        "actions": [action],
    }


def build_context_collection(
    user_id: uuid.UUID,
    items: list[ContextRecord],
) -> dict[str, Any]:
    """Build a Siren context collection; item entities link to detail (no nested actions)."""
    entities: list[dict[str, Any]] = []
    for record in items:
        href = _item_href(record.id)
        entities.append(
            {
                "class": ["context", "item"],
                "rel": ["item"],
                "href": href,
                "properties": {
                    "id": str(record.id),
                    "title": record.title,
                    "body": record.body,
                },
                "links": [{"rel": ["self"], "href": href}],
            }
        )
    return {
        "class": ["context", "collection"],
        "properties": {"user_id": str(user_id)},
        "entities": entities,
        "links": [{"rel": [rel], "href": href} for rel, href in _COLLECTION_LINKS],
        "actions": [dict(ADD_CONTEXT_ACTION)],
    }
