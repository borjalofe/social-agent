"""ADK `copy_medium` specialist: draft Medium long-form copy only (no publish/approve)."""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import Agent
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider

COPY_MEDIUM_NAME = "copy_medium"
COPY_MEDIUM_CHANNEL = "medium"
DEFAULT_COPY_MEDIUM_MODEL = "gemini-2.0-flash"

COPY_MEDIUM_DESCRIPTION = (
    "Drafts Medium articles in the user's voice; does not publish or approve."
)

COPY_MEDIUM_BASE_INSTRUCTION = """\
You are the Social Agent Medium copy specialist (`copy_medium`).

Responsibilities:
- Draft Medium articles that match the editorial voice, context, and channel rules below.
- Return draft copy only. Do not publish, schedule, or call external APIs.
- Do not invent credentials, approvals, or facts absent from the brief / context.

Medium craft:
- Strong title + subtitle; narrative arc with short Markdown sections.
- Prefer EN syndication-ready structure when the brief is bilingual
  (canonical may live on the blog).
- One primary idea; concrete detail over hype. Not a LinkedIn employment funnel; not a tweet.
- Follow channel rules when present; if voice/context is "(none)", ask for what's missing
  instead of inventing a brand voice.

Security:
- Least privilege: draft text only. Never request or echo secrets.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_COPY_MEDIUM_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_COPY_MEDIUM_MODEL),
    )


def build_copy_medium_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
) -> Agent:
    """Build the Medium specialist. Inject InstructionProvider for per-user packs."""
    instruction: str | InstructionFn
    if instruction_provider is not None:
        instruction = instruction_provider.for_agent(
            COPY_MEDIUM_BASE_INSTRUCTION,
            channel=COPY_MEDIUM_CHANNEL,
        )
    else:
        instruction = COPY_MEDIUM_BASE_INSTRUCTION

    return Agent(
        name=COPY_MEDIUM_NAME,
        description=COPY_MEDIUM_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
        ),
    )


copy_medium_agent = build_copy_medium_agent()
