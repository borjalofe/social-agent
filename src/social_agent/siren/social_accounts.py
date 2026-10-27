"""Siren `social-accounts` collection + item (one binding per user+channel)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

_COLLECTION_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/social-accounts"),
    ("home", "/"),
)

EXPECTED_SOCIAL_ACCOUNTS_COLLECTION_RELS: frozenset[tuple[str, ...]] = frozenset(
    ((rel,) for rel, _href in _COLLECTION_LINKS)
)

ADD_SOCIAL_ACCOUNT_ACTION: dict[str, Any] = {
    "name": "add-social-account",
    "method": "POST",
    "href": "/social-accounts",
    "type": "application/json",
    "fields": [
        {"name": "channel", "type": "text"},
        {"name": "handle", "type": "text"},
        {"name": "credentials", "type": "text"},
    ],
}

UPDATE_SOCIAL_ACCOUNT_ACTION: dict[str, Any] = {
    "name": "update-social-account",
    "method": "PUT",
    "href": "",  # filled per item
    "type": "application/json",
    "fields": [
        {"name": "handle", "type": "text"},
        {"name": "credentials", "type": "text"},
    ],
}


@dataclass(frozen=True)
class SocialAccountRecord:
    user_id: uuid.UUID
    channel: str
    handle: str
    credentials_encrypted: str


class SocialAccountStore(Protocol):
    def list(self, user_id: uuid.UUID) -> list[SocialAccountRecord]: ...

    def get(self, user_id: uuid.UUID, channel: str) -> SocialAccountRecord | None: ...

    def create(
        self,
        user_id: uuid.UUID,
        *,
        channel: str,
        handle: str,
        credentials_encrypted: str,
    ) -> SocialAccountRecord | None:
        """Return the new record, or None if (user_id, channel) already exists."""

    def update(
        self,
        user_id: uuid.UUID,
        channel: str,
        *,
        handle: str,
        credentials_encrypted: str,
    ) -> SocialAccountRecord | None:
        """Return the updated record, or None if missing for this user."""


class InMemorySocialAccountStore:
    """Process-local social accounts (inject a durable store for production)."""

    def __init__(self) -> None:
        self._accounts: dict[tuple[uuid.UUID, str], SocialAccountRecord] = {}

    def list(self, user_id: uuid.UUID) -> list[SocialAccountRecord]:
        return [acct for (uid, _), acct in self._accounts.items() if uid == user_id]

    def get(self, user_id: uuid.UUID, channel: str) -> SocialAccountRecord | None:
        return self._accounts.get((user_id, channel))

    def create(
        self,
        user_id: uuid.UUID,
        *,
        channel: str,
        handle: str,
        credentials_encrypted: str,
    ) -> SocialAccountRecord | None:
        key = (user_id, channel)
        if key in self._accounts:
            return None
        record = SocialAccountRecord(
            user_id=user_id,
            channel=channel,
            handle=handle,
            credentials_encrypted=credentials_encrypted,
        )
        self._accounts[key] = record
        return record

    def update(
        self,
        user_id: uuid.UUID,
        channel: str,
        *,
        handle: str,
        credentials_encrypted: str,
    ) -> SocialAccountRecord | None:
        key = (user_id, channel)
        if key not in self._accounts:
            return None
        record = SocialAccountRecord(
            user_id=user_id,
            channel=channel,
            handle=handle,
            credentials_encrypted=credentials_encrypted,
        )
        self._accounts[key] = record
        return record


def _item_href(channel: str) -> str:
    return f"/social-accounts/{channel}"


def _public_properties(record: SocialAccountRecord) -> dict[str, Any]:
    # Never expose plaintext or ciphertext credentials in Siren bodies (DEC-002).
    return {
        "user_id": str(record.user_id),
        "channel": record.channel,
        "handle": record.handle,
        "credentials_set": bool(record.credentials_encrypted),
    }


def build_social_account_item(record: SocialAccountRecord) -> dict[str, Any]:
    """Build a Siren social-account item (no credential material)."""
    href = _item_href(record.channel)
    action = {**UPDATE_SOCIAL_ACCOUNT_ACTION, "href": href}
    return {
        "class": ["social-account", "item"],
        "properties": _public_properties(record),
        "entities": [],
        "links": [
            {"rel": ["self"], "href": href},
            {"rel": ["collection"], "href": "/social-accounts"},
            {"rel": ["home"], "href": "/"},
        ],
        "actions": [action],
    }


def build_social_accounts_collection(
    user_id: uuid.UUID,
    items: list[SocialAccountRecord],
) -> dict[str, Any]:
    """Build a Siren social-accounts collection; items link to detail (no nested actions)."""
    entities: list[dict[str, Any]] = []
    for record in items:
        href = _item_href(record.channel)
        entities.append(
            {
                "class": ["social-account", "item"],
                "rel": ["item"],
                "href": href,
                "properties": {
                    "channel": record.channel,
                    "handle": record.handle,
                    "credentials_set": bool(record.credentials_encrypted),
                },
                "links": [{"rel": ["self"], "href": href}],
            }
        )
    return {
        "class": ["social-accounts", "collection"],
        "properties": {"user_id": str(user_id)},
        "entities": entities,
        "links": [{"rel": [rel], "href": href} for rel, href in _COLLECTION_LINKS],
        "actions": [dict(ADD_SOCIAL_ACCOUNT_ACTION)],
    }
