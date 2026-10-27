"""Siren `canal-rules` collection + item (one body per user+channel)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

_COLLECTION_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/canal-rules"),
    ("home", "/"),
)

EXPECTED_CANAL_RULES_COLLECTION_RELS: frozenset[tuple[str, ...]] = frozenset(
    ((rel,) for rel, _href in _COLLECTION_LINKS)
)

ADD_CANAL_RULE_ACTION: dict[str, Any] = {
    "name": "add-canal-rule",
    "method": "POST",
    "href": "/canal-rules",
    "type": "application/json",
    "fields": [
        {"name": "channel", "type": "text"},
        {"name": "body", "type": "text"},
    ],
}

UPDATE_CANAL_RULE_ACTION: dict[str, Any] = {
    "name": "update-canal-rule",
    "method": "PUT",
    "href": "",  # filled per item
    "type": "application/json",
    "fields": [{"name": "body", "type": "text"}],
}


@dataclass(frozen=True)
class CanalRuleRecord:
    user_id: uuid.UUID
    channel: str
    body: str


class CanalRuleStore(Protocol):
    def list(self, user_id: uuid.UUID) -> list[CanalRuleRecord]: ...

    def get(self, user_id: uuid.UUID, channel: str) -> CanalRuleRecord | None: ...

    def create(self, user_id: uuid.UUID, *, channel: str, body: str) -> CanalRuleRecord | None:
        """Return the new record, or None if (user_id, channel) already exists."""

    def update(self, user_id: uuid.UUID, channel: str, *, body: str) -> CanalRuleRecord | None:
        """Return the updated record, or None if missing for this user."""


class InMemoryCanalRuleStore:
    """Process-local canal rules (inject a durable store for production)."""

    def __init__(self) -> None:
        self._rules: dict[tuple[uuid.UUID, str], CanalRuleRecord] = {}

    def list(self, user_id: uuid.UUID) -> list[CanalRuleRecord]:
        return [rule for (uid, _), rule in self._rules.items() if uid == user_id]

    def get(self, user_id: uuid.UUID, channel: str) -> CanalRuleRecord | None:
        return self._rules.get((user_id, channel))

    def create(self, user_id: uuid.UUID, *, channel: str, body: str) -> CanalRuleRecord | None:
        key = (user_id, channel)
        if key in self._rules:
            return None
        record = CanalRuleRecord(user_id=user_id, channel=channel, body=body)
        self._rules[key] = record
        return record

    def update(self, user_id: uuid.UUID, channel: str, *, body: str) -> CanalRuleRecord | None:
        key = (user_id, channel)
        if key not in self._rules:
            return None
        record = CanalRuleRecord(user_id=user_id, channel=channel, body=body)
        self._rules[key] = record
        return record


def _item_href(channel: str) -> str:
    return f"/canal-rules/{channel}"


def build_canal_rule_item(record: CanalRuleRecord) -> dict[str, Any]:
    """Build a Siren canal-rule item with update-canal-rule action."""
    href = _item_href(record.channel)
    action = {**UPDATE_CANAL_RULE_ACTION, "href": href}
    return {
        "class": ["canal-rule", "item"],
        "properties": {
            "user_id": str(record.user_id),
            "channel": record.channel,
            "body": record.body,
        },
        "entities": [],
        "links": [
            {"rel": ["self"], "href": href},
            {"rel": ["collection"], "href": "/canal-rules"},
            {"rel": ["home"], "href": "/"},
        ],
        "actions": [action],
    }


def build_canal_rules_collection(
    user_id: uuid.UUID,
    items: list[CanalRuleRecord],
) -> dict[str, Any]:
    """Build a Siren canal-rules collection; items link to detail (no nested actions)."""
    entities: list[dict[str, Any]] = []
    for record in items:
        href = _item_href(record.channel)
        entities.append(
            {
                "class": ["canal-rule", "item"],
                "rel": ["item"],
                "href": href,
                "properties": {
                    "channel": record.channel,
                    "body": record.body,
                },
                "links": [{"rel": ["self"], "href": href}],
            }
        )
    return {
        "class": ["canal-rules", "collection"],
        "properties": {"user_id": str(user_id)},
        "entities": entities,
        "links": [{"rel": [rel], "href": href} for rel, href in _COLLECTION_LINKS],
        "actions": [dict(ADD_CANAL_RULE_ACTION)],
    }
