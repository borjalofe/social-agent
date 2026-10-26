"""Siren `home` entry resource (catalog links)."""

from __future__ import annotations

import uuid
from typing import Any

SIREN_MEDIA_TYPE = "application/vnd.siren+json"

# Entry map for M2 resources (handlers land in later one-resource PRs).
_HOME_LINKS: tuple[tuple[str, str], ...] = (
    ("self", "/"),
    ("user", "/user"),
    ("voice", "/voice"),
    ("context", "/context"),
    ("canal-rules", "/canal-rules"),
    ("social-accounts", "/social-accounts"),
    ("llm-connections", "/llm-connections"),
    ("publications", "/publications"),
    ("agent-run", "/agent-run"),
)

EXPECTED_HOME_RELS: frozenset[tuple[str, ...]] = frozenset(((rel,) for rel, _href in _HOME_LINKS))


def build_home(
    user_id: uuid.UUID,
    *,
    email: str | None = None,
) -> dict[str, Any]:
    """Build the Siren home entity: entry point + links to known resources."""
    properties: dict[str, Any] = {
        "title": "Social Agent",
        "user_id": str(user_id),
    }
    if email is not None:
        properties["email"] = email
    return {
        "class": ["home"],
        "properties": properties,
        "entities": [],
        "links": [{"rel": [rel], "href": href} for rel, href in _HOME_LINKS],
        "actions": [],
    }
