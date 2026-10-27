"""Approve an agent-run draft into a persisted publication (calendar final)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from social_agent.siren.agent_run import AgentRunPayloadStore, AgentRunRecord, AgentRunStore
from social_agent.siren.publications import PublicationRecord, PublicationStore

APPROVABLE_RUN_STATUSES = frozenset({"open", "waiting_approval"})


@dataclass(frozen=True)
class DraftContent:
    body: str
    title: str | None
    channel: str


class ApproveDraftError(ValueError):
    """Domain error while approving a draft (map to HTTP in the API layer)."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def extract_draft_content(
    record: AgentRunRecord,
    payload: dict[str, Any],
) -> DraftContent:
    """Pull title/body/channel from payload.draft (+ session channel fallback)."""
    raw = payload.get("draft")
    title: str | None = None
    body: str | None = None
    channel: str | None = record.channel

    if isinstance(raw, str):
        body = raw.strip() or None
    elif isinstance(raw, dict):
        raw_body = raw.get("body")
        if isinstance(raw_body, str) and raw_body.strip():
            body = raw_body.strip()
        raw_title = raw.get("title")
        if isinstance(raw_title, str) and raw_title.strip():
            title = raw_title.strip()
        raw_channel = raw.get("channel")
        if isinstance(raw_channel, str) and raw_channel.strip():
            channel = raw_channel.strip()

    if channel is None or not str(channel).strip():
        payload_channel = payload.get("channel")
        if isinstance(payload_channel, str) and payload_channel.strip():
            channel = payload_channel.strip()

    if body is None:
        raise ApproveDraftError("draft_missing")
    if channel is None or not channel.strip():
        raise ApproveDraftError("channel_missing")

    return DraftContent(body=body, title=title, channel=channel.strip())


def approve_draft(
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    *,
    agent_run_store: AgentRunStore,
    payload_store: AgentRunPayloadStore,
    publication_store: PublicationStore,
) -> tuple[AgentRunRecord, PublicationRecord, dict[str, Any]]:
    """Persist draft as `approved` publication; mark run `completed`.

    Returns (updated_run, publication, updated_payload).
    """
    record = agent_run_store.get(user_id, run_id)
    if record is None:
        raise ApproveDraftError("not_found")
    if record.status not in APPROVABLE_RUN_STATUSES:
        raise ApproveDraftError("not_approvable")

    payload = payload_store.get(run_id) or {}
    draft = extract_draft_content(record, payload)

    publication = publication_store.create(
        user_id,
        channel=draft.channel,
        title=draft.title,
        body=draft.body,
        status="approved",
        scheduled_at=None,
        published_at=None,
    )

    updated_run = agent_run_store.update_status(user_id, run_id, status="completed")
    if updated_run is None:
        raise ApproveDraftError("not_found")

    next_payload = dict(payload)
    next_payload["publication_id"] = str(publication.id)
    next_payload["approved"] = True
    payload_store.put(run_id, next_payload)

    return updated_run, publication, next_payload
