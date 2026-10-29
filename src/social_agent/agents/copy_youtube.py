"""ADK `copy_youtube` specialist: draft YouTube scripts/metadata only (no publish/approve)."""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import Agent
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider

COPY_YOUTUBE_NAME = "copy_youtube"
COPY_YOUTUBE_CHANNEL = "youtube"
DEFAULT_COPY_YOUTUBE_MODEL = "gemini-2.0-flash"

COPY_YOUTUBE_DESCRIPTION = (
    "Drafts YouTube titles, descriptions, and scripts in the user's voice; "
    "does not publish or approve."
)

COPY_YOUTUBE_BASE_INSTRUCTION = """\
You are the Social Agent YouTube copy specialist (`copy_youtube`).

Responsibilities:
- Draft YouTube titles, descriptions, and spoken scripts that match the editorial voice,
  context, and channel rules below.
- Return draft copy only. Do not publish, schedule, or call external APIs.
- Do not invent credentials, approvals, or facts absent from the brief / context.

YouTube craft:
- Strong title + description; spoken script with a clear hook in the first ~15 seconds.
- Optional chapter outline when the brief asks for structure.
- One primary idea; concrete demo/detail over hype. Not a LinkedIn funnel; not a tweet;
  not a Medium essay pasted into a teleprompter.
- Follow channel rules when present; if voice/context is "(none)", ask for what's missing
  instead of inventing a brand voice.

Security:
- Least privilege: draft text only. Never request or echo secrets.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_COPY_YOUTUBE_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_COPY_YOUTUBE_MODEL),
    )


def build_copy_youtube_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
) -> Agent:
    """Build the YouTube specialist. Inject InstructionProvider for per-user packs."""
    instruction: str | InstructionFn
    if instruction_provider is not None:
        instruction = instruction_provider.for_agent(
            COPY_YOUTUBE_BASE_INSTRUCTION,
            channel=COPY_YOUTUBE_CHANNEL,
        )
    else:
        instruction = COPY_YOUTUBE_BASE_INSTRUCTION

    return Agent(
        name=COPY_YOUTUBE_NAME,
        description=COPY_YOUTUBE_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
        ),
    )


copy_youtube_agent = build_copy_youtube_agent()
