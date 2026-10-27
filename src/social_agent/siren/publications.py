"""Siren `publications` collection + item (approved finals; calendar fields)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

_COLLECTION_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/publications"),
    ("home", "/"),
)

EXPECTED_PUBLICATIONS_COLLECTION_RELS: frozenset[tuple[str, ...]] = frozenset(
    ((rel,) for rel, _href in _COLLECTION_LINKS)
)

ALLOWED_PUBLICATION_STATUSES = frozenset({"approved", "scheduled", "published"})
LOCKED_PUBLICATION_STATUSES = frozenset({"scheduled", "published"})


def is_publication_locked(status: str) -> bool:
    """True when the publication may not be edited (calendar / already out)."""
    return status in LOCKED_PUBLICATION_STATUSES


ADD_PUBLICATION_ACTION: dict[str, Any] = {
    "name": "add-publication",
    "method": "POST",
    "href": "/publications",
    "type": "application/json",
    "fields": [
        {"name": "channel", "type": "text"},
        {"name": "title", "type": "text"},
        {"name": "body", "type": "text"},
        {"name": "status", "type": "text"},
        {"name": "scheduled_at", "type": "text"},
        {"name": "published_at", "type": "text"},
    ],
}

UPDATE_PUBLICATION_ACTION: dict[str, Any] = {
    "name": "update-publication",
    "method": "PUT",
    "href": "",  # filled per item
    "type": "application/json",
    "fields": [
        {"name": "channel", "type": "text"},
        {"name": "title", "type": "text"},
        {"name": "body", "type": "text"},
        {"name": "status", "type": "text"},
        {"name": "scheduled_at", "type": "text"},
        {"name": "published_at", "type": "text"},
    ],
}


@dataclass(frozen=True)
class PublicationRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    channel: str
    title: str | None
    body: str
    status: str
    scheduled_at: datetime | None
    published_at: datetime | None


class PublicationStore(Protocol):
    def list(self, user_id: uuid.UUID) -> list[PublicationRecord]: ...

    def get(self, user_id: uuid.UUID, pub_id: uuid.UUID) -> PublicationRecord | None: ...

    def create(
        self,
        user_id: uuid.UUID,
        *,
        channel: str,
        title: str | None,
        body: str,
        status: str,
        scheduled_at: datetime | None,
        published_at: datetime | None,
    ) -> PublicationRecord: ...

    def update(
        self,
        user_id: uuid.UUID,
        pub_id: uuid.UUID,
        *,
        channel: str,
        title: str | None,
        body: str,
        status: str,
        scheduled_at: datetime | None,
        published_at: datetime | None,
    ) -> PublicationRecord | None: ...


class InMemoryPublicationStore:
    """Process-local publications (inject a durable store for production)."""

    def __init__(self) -> None:
        self._pubs: dict[uuid.UUID, PublicationRecord] = {}

    def list(self, user_id: uuid.UUID) -> list[PublicationRecord]:
        return [pub for pub in self._pubs.values() if pub.user_id == user_id]

    def get(self, user_id: uuid.UUID, pub_id: uuid.UUID) -> PublicationRecord | None:
        pub = self._pubs.get(pub_id)
        if pub is None or pub.user_id != user_id:
            return None
        return pub

    def create(
        self,
        user_id: uuid.UUID,
        *,
        channel: str,
        title: str | None,
        body: str,
        status: str,
        scheduled_at: datetime | None,
        published_at: datetime | None,
    ) -> PublicationRecord:
        record = PublicationRecord(
            id=uuid.uuid4(),
            user_id=user_id,
            channel=channel,
            title=title,
            body=body,
            status=status,
            scheduled_at=scheduled_at,
            published_at=published_at,
        )
        self._pubs[record.id] = record
        return record

    def update(
        self,
        user_id: uuid.UUID,
        pub_id: uuid.UUID,
        *,
        channel: str,
        title: str | None,
        body: str,
        status: str,
        scheduled_at: datetime | None,
        published_at: datetime | None,
    ) -> PublicationRecord | None:
        if self.get(user_id, pub_id) is None:
            return None
        record = PublicationRecord(
            id=pub_id,
            user_id=user_id,
            channel=channel,
            title=title,
            body=body,
            status=status,
            scheduled_at=scheduled_at,
            published_at=published_at,
        )
        self._pubs[pub_id] = record
        return record


def _item_href(pub_id: uuid.UUID) -> str:
    return f"/publications/{pub_id}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _properties(record: PublicationRecord) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "user_id": str(record.user_id),
        "channel": record.channel,
        "title": record.title,
        "body": record.body,
        "status": record.status,
        "scheduled_at": _iso(record.scheduled_at),
        "published_at": _iso(record.published_at),
    }


def build_publication_item(record: PublicationRecord) -> dict[str, Any]:
    """Build a Siren publication item; omit update when scheduled/published."""
    href = _item_href(record.id)
    actions: list[dict[str, Any]] = []
    if not is_publication_locked(record.status):
        actions.append({**UPDATE_PUBLICATION_ACTION, "href": href})
    return {
        "class": ["publication", "item"],
        "properties": _properties(record),
        "entities": [],
        "links": [
            {"rel": ["self"], "href": href},
            {"rel": ["collection"], "href": "/publications"},
            {"rel": ["home"], "href": "/"},
        ],
        "actions": actions,
    }


def build_publications_collection(
    user_id: uuid.UUID,
    items: list[PublicationRecord],
) -> dict[str, Any]:
    """Build a Siren publications collection; items link to detail (no nested actions)."""
    entities: list[dict[str, Any]] = []
    for record in items:
        href = _item_href(record.id)
        entities.append(
            {
                "class": ["publication", "item"],
                "rel": ["item"],
                "href": href,
                "properties": {
                    "id": str(record.id),
                    "channel": record.channel,
                    "title": record.title,
                    "status": record.status,
                    "scheduled_at": _iso(record.scheduled_at),
                    "published_at": _iso(record.published_at),
                },
                "links": [{"rel": ["self"], "href": href}],
            }
        )
    return {
        "class": ["publications", "collection"],
        "properties": {"user_id": str(user_id)},
        "entities": entities,
        "links": [{"rel": [rel], "href": href} for rel, href in _COLLECTION_LINKS],
        "actions": [dict(ADD_PUBLICATION_ACTION)],
    }
