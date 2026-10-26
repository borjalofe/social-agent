"""Siren `user` profile resource (caller's own profile)."""

from __future__ import annotations

import uuid
from typing import Any

_USER_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/user"),
    ("home", "/"),
)

EXPECTED_USER_RELS: frozenset[tuple[str, ...]] = frozenset(((rel,) for rel, _href in _USER_LINKS))


def build_user(
    user_id: uuid.UUID,
    *,
    email: str | None = None,
) -> dict[str, Any]:
    """Build the Siren user entity for the authenticated subject (never secrets)."""
    properties: dict[str, Any] = {
        "user_id": str(user_id),
    }
    if email is not None:
        properties["email"] = email
    return {
        "class": ["user"],
        "properties": properties,
        "entities": [],
        "links": [{"rel": [rel], "href": href} for rel, href in _USER_LINKS],
        "actions": [],
    }
