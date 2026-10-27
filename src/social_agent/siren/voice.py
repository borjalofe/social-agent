"""Siren `voice` resource: editorial voice body + update-voice action."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

_VOICE_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/voice"),
    ("home", "/"),
)

EXPECTED_VOICE_RELS: frozenset[tuple[str, ...]] = frozenset(((rel,) for rel, _href in _VOICE_LINKS))

UPDATE_VOICE_ACTION: dict[str, Any] = {
    "name": "update-voice",
    "method": "PUT",
    "href": "/voice",
    "type": "application/json",
    "fields": [{"name": "body", "type": "text"}],
}


@dataclass(frozen=True)
class VoiceRecord:
    user_id: uuid.UUID
    body: str


class VoiceStore(Protocol):
    def get(self, user_id: uuid.UUID) -> VoiceRecord | None: ...

    def put(self, user_id: uuid.UUID, body: str) -> VoiceRecord: ...


class InMemoryVoiceStore:
    """Process-local voice bodies (inject a durable store for production)."""

    def __init__(self) -> None:
        self._bodies: dict[uuid.UUID, str] = {}

    def get(self, user_id: uuid.UUID) -> VoiceRecord | None:
        if user_id not in self._bodies:
            return None
        return VoiceRecord(user_id=user_id, body=self._bodies[user_id])

    def put(self, user_id: uuid.UUID, body: str) -> VoiceRecord:
        self._bodies[user_id] = body
        return VoiceRecord(user_id=user_id, body=body)


def build_voice(
    user_id: uuid.UUID,
    *,
    body: str = "",
) -> dict[str, Any]:
    """Build the Siren voice entity for the authenticated subject."""
    return {
        "class": ["voice"],
        "properties": {
            "user_id": str(user_id),
            "body": body,
        },
        "entities": [],
        "links": [{"rel": [rel], "href": href} for rel, href in _VOICE_LINKS],
        "actions": [dict(UPDATE_VOICE_ACTION)],
    }
