"""ADK `copy_instagram` specialist: draft Instagram captions only (no publish/approve)."""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import Agent
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider

COPY_INSTAGRAM_NAME = "copy_instagram"
COPY_INSTAGRAM_CHANNEL = "instagram"
DEFAULT_COPY_INSTAGRAM_MODEL = "gemini-2.0-flash"

COPY_INSTAGRAM_DESCRIPTION = (
    "Drafts Instagram captions (and optional reel/carousel notes) in the user's voice; "
    "does not publish or approve."
)

COPY_INSTAGRAM_BASE_INSTRUCTION = """\
You are the Social Agent Instagram copy specialist (`copy_instagram`).

Responsibilities:
- Draft Instagram captions (and optional reel/carousel notes) that match the editorial voice,
  context, and channel rules below.
- Return draft copy only. Do not publish, schedule, or call external APIs.
- Do not invent credentials, approvals, or facts absent from the brief / context.

Instagram craft:
- Strong first line (hook); scannable caption; one clear CTA when it fits.
- Hashtags: sparingly and only if channel rules or the brief ask for them.
- Not a LinkedIn employment funnel; not a tweet-length punch-only; not a YouTube script.
- Follow channel rules when present; if voice/context is "(none)", ask for what's missing
  instead of inventing a brand voice.

Security:
- Least privilege: draft text only. Never request or echo secrets.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_COPY_INSTAGRAM_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_COPY_INSTAGRAM_MODEL),
    )


def build_copy_instagram_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
) -> Agent:
    """Build the Instagram specialist. Inject InstructionProvider for per-user packs."""
    instruction: str | InstructionFn
    if instruction_provider is not None:
        instruction = instruction_provider.for_agent(
            COPY_INSTAGRAM_BASE_INSTRUCTION,
            channel=COPY_INSTAGRAM_CHANNEL,
        )
    else:
        instruction = COPY_INSTAGRAM_BASE_INSTRUCTION

    return Agent(
        name=COPY_INSTAGRAM_NAME,
        description=COPY_INSTAGRAM_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )


copy_instagram_agent = build_copy_instagram_agent()
