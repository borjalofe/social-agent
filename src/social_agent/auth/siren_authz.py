"""Siren action authorization: filter affordances and enforce 403."""

from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class SirenAction:
    """One Siren action affordance (name + HTTP method + href)."""

    name: str
    method: str
    href: str


class ForbiddenError(PermissionError):
    """Subject may not perform this Siren action (HTTP 403)."""

    status_code = 403

    def __init__(
        self,
        message: str = "forbidden",
        *,
        action: str | None = None,
    ) -> None:
        self.action = action
        super().__init__(message)


class ActionPolicy(Protocol):
    def allows(
        self,
        subject_id: uuid.UUID,
        *,
        resource_owner_id: uuid.UUID,
        action: str,
    ) -> bool: ...


class OwnerOnlyPolicy:
    """M2 default: subject may act only on resources they own."""

    def allows(
        self,
        subject_id: uuid.UUID,
        *,
        resource_owner_id: uuid.UUID,
        action: str,
    ) -> bool:
        del action  # ownership is the gate; per-action roles land with admin (#62)
        return subject_id == resource_owner_id


class SirenActionAuthz:
    """Filter Siren actions by policy and enforce unauthorized attempts as 403."""

    def __init__(self, policy: ActionPolicy | None = None) -> None:
        self._policy: ActionPolicy = policy if policy is not None else OwnerOnlyPolicy()

    def filter_actions(
        self,
        subject_id: uuid.UUID,
        *,
        resource_owner_id: uuid.UUID,
        candidates: Sequence[SirenAction],
    ) -> list[SirenAction]:
        return [
            action
            for action in candidates
            if self._policy.allows(
                subject_id,
                resource_owner_id=resource_owner_id,
                action=action.name,
            )
        ]

    def enforce(
        self,
        subject_id: uuid.UUID,
        *,
        resource_owner_id: uuid.UUID,
        action: str,
    ) -> None:
        if not self._policy.allows(
            subject_id,
            resource_owner_id=resource_owner_id,
            action=action,
        ):
            raise ForbiddenError("forbidden", action=action)

    def authorize_entity(
        self,
        entity: Mapping[str, Any],
        subject_id: uuid.UUID,
        *,
        resource_owner_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Return a deep copy of a Siren entity with only authorized `actions`."""
        out = copy.deepcopy(dict(entity))
        raw_actions = out.get("actions")
        if not isinstance(raw_actions, list):
            out["actions"] = []
            return out
        kept: list[Any] = []
        for item in raw_actions:
            if not isinstance(item, Mapping):
                continue
            name = item.get("name")
            if not isinstance(name, str):
                continue
            if self._policy.allows(
                subject_id,
                resource_owner_id=resource_owner_id,
                action=name,
            ):
                kept.append(copy.deepcopy(dict(item)))
        out["actions"] = kept
        return out
