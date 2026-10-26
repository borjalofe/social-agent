"""Siren action authz: filter affordances and enforce 403."""

from __future__ import annotations

import uuid

import pytest

from social_agent.auth.siren_authz import (
    ForbiddenError,
    SirenAction,
    SirenActionAuthz,
)


@pytest.fixture()
def authz() -> SirenActionAuthz:
    return SirenActionAuthz()


@pytest.fixture()
def owner() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def stranger() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def candidates() -> list[SirenAction]:
    return [
        SirenAction(name="update-voice", method="PUT", href="/voice"),
        SirenAction(name="run-copy-linkedin", method="POST", href="/agent-run"),
    ]


def test_owner_sees_all_candidate_actions(
    authz: SirenActionAuthz,
    owner: uuid.UUID,
    candidates: list[SirenAction],
) -> None:
    allowed = authz.filter_actions(
        owner,
        resource_owner_id=owner,
        candidates=candidates,
    )
    assert allowed == candidates


def test_non_owner_sees_no_actions(
    authz: SirenActionAuthz,
    owner: uuid.UUID,
    stranger: uuid.UUID,
    candidates: list[SirenAction],
) -> None:
    allowed = authz.filter_actions(
        stranger,
        resource_owner_id=owner,
        candidates=candidates,
    )
    assert allowed == []


def test_enforce_allows_owner(
    authz: SirenActionAuthz,
    owner: uuid.UUID,
) -> None:
    authz.enforce(owner, resource_owner_id=owner, action="update-voice")


def test_enforce_rejects_non_owner_with_403(
    authz: SirenActionAuthz,
    owner: uuid.UUID,
    stranger: uuid.UUID,
) -> None:
    with pytest.raises(ForbiddenError) as exc_info:
        authz.enforce(stranger, resource_owner_id=owner, action="update-voice")
    assert exc_info.value.status_code == 403
    assert exc_info.value.action == "update-voice"


def test_authorize_entity_keeps_actions_for_owner(
    authz: SirenActionAuthz,
    owner: uuid.UUID,
) -> None:
    entity = {
        "class": ["voice"],
        "properties": {"body": "…"},
        "actions": [
            {"name": "update-voice", "method": "PUT", "href": "/voice"},
        ],
    }
    out = authz.authorize_entity(entity, owner, resource_owner_id=owner)
    assert out["actions"] == entity["actions"]
    assert out is not entity


def test_authorize_entity_strips_actions_for_non_owner(
    authz: SirenActionAuthz,
    owner: uuid.UUID,
    stranger: uuid.UUID,
) -> None:
    entity = {
        "class": ["voice"],
        "properties": {"body": "…"},
        "actions": [
            {"name": "update-voice", "method": "PUT", "href": "/voice"},
        ],
    }
    out = authz.authorize_entity(entity, stranger, resource_owner_id=owner)
    assert out["actions"] == []
    assert entity["actions"]  # original untouched
