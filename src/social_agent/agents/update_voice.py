"""ADK `update_voice` specialist: draft editorial voice from publications corpus."""

from __future__ import annotations

import os
import uuid
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.readonly_context import ReadonlyContext
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider
from social_agent.siren.publications import PublicationRecord, PublicationStore

UPDATE_VOICE_NAME = "update_voice"
DEFAULT_UPDATE_VOICE_MODEL = "gemini-2.0-flash"

UPDATE_VOICE_DESCRIPTION = (
    "Drafts an updated editorial voice document from the user's publications corpus; "
    "does not publish, approve, or write network copy."
)

UPDATE_VOICE_BASE_INSTRUCTION = """\
You are the Social Agent voice-update specialist (`update_voice`).

Responsibilities:
- Analyze the current editorial voice and the publications corpus below.
- Draft an updated voice document (form patterns: openings, sentence length, closures,
  characteristic moves, vocabulary). Prefer evidence from the corpus; mark SUPUESTO
  anything invented for lack of material.
- Return draft voice text only. Do not publish, schedule, approve, or call external APIs.
- Do not write network copy (LinkedIn/X/blog/etc.). Do not invent credentials.

Corpus craft:
- Weight approved / published publications more than empty titles.
- Extract form patterns, not just topics. Cite short examples from the corpus.
- Privacy: language patterns only — never echo client names, credentials, or secrets
  that might appear in bodies.

Security:
- Least privilege: draft voice text only. Never request or echo secrets.
- The human applies the draft via Siren `PUT /voice` (update-voice); you do not write stores.
"""


def format_publications_corpus(pubs: list[PublicationRecord]) -> str:
    """Render publications as an instruction section (corpus for voice analysis)."""
    if not pubs:
        return "## Publications corpus\n(none)\n"
    chunks = ["## Publications corpus"]
    for pub in pubs:
        title = pub.title.strip() if pub.title else "(untitled)"
        chunks.append(
            f"### [{pub.channel}] {title} ({pub.status})\n{pub.body}".rstrip()
        )
    return "\n\n".join(chunks).rstrip() + "\n"


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_UPDATE_VOICE_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_UPDATE_VOICE_MODEL),
    )


def _instruction_with_corpus(
    *,
    instruction_provider: InstructionProvider,
    publication_store: PublicationStore,
) -> InstructionFn:
    def _instruction(ctx: ReadonlyContext) -> str:
        try:
            user_id = uuid.UUID(str(ctx.user_id))
        except (TypeError, ValueError):
            return UPDATE_VOICE_BASE_INSTRUCTION

        packed = instruction_provider.pack(
            user_id,
            channel=None,
            base_instruction=UPDATE_VOICE_BASE_INSTRUCTION,
        )
        corpus = format_publications_corpus(publication_store.list(user_id))
        return packed.rstrip() + "\n\n" + corpus

    return _instruction


def build_update_voice_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
    publication_store: PublicationStore | None = None,
) -> Agent:
    """Build the voice-update specialist.

    Inject InstructionProvider + PublicationStore to pack current voice and corpus.
    """
    instruction: str | InstructionFn
    if instruction_provider is not None and publication_store is not None:
        instruction = _instruction_with_corpus(
            instruction_provider=instruction_provider,
            publication_store=publication_store,
        )
    elif instruction_provider is not None:
        instruction = instruction_provider.for_agent(UPDATE_VOICE_BASE_INSTRUCTION)
    else:
        instruction = UPDATE_VOICE_BASE_INSTRUCTION

    return Agent(
        name=UPDATE_VOICE_NAME,
        description=UPDATE_VOICE_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.4,
            max_output_tokens=4096,
        ),
    )


update_voice_agent = build_update_voice_agent()
