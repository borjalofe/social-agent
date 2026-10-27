"""ADK `copy_linkedin` specialist: draft LinkedIn copy only (no publish/approve)."""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import Agent
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider

COPY_LINKEDIN_NAME = "copy_linkedin"
COPY_LINKEDIN_CHANNEL = "linkedin"
DEFAULT_COPY_LINKEDIN_MODEL = "gemini-2.0-flash"

COPY_LINKEDIN_DESCRIPTION = (
    "Drafts LinkedIn posts in the user's voice; does not publish or approve."
)

COPY_LINKEDIN_BASE_INSTRUCTION = """\
You are the Social Agent LinkedIn copy specialist (`copy_linkedin`).

Responsibilities:
- Draft LinkedIn posts that match the editorial voice, context, and channel rules below.
- Return draft copy only. Do not publish, schedule, or call external APIs.
- Do not invent credentials, approvals, or facts absent from the brief / context.

LinkedIn craft:
- Strong first line (hook). Short paragraphs. Scannable.
- One clear idea; optional single open question as CTA.
- Follow channel rules when present; if voice/context is "(none)", ask for what's missing
  instead of inventing a brand voice.

Security:
- Least privilege: draft text only. Never request or echo secrets.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_COPY_LINKEDIN_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_COPY_LINKEDIN_MODEL),
    )


def build_copy_linkedin_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
) -> Agent:
    """Build the LinkedIn specialist. Inject InstructionProvider for per-user packs."""
    instruction: str | InstructionFn
    if instruction_provider is not None:
        instruction = instruction_provider.for_agent(
            COPY_LINKEDIN_BASE_INSTRUCTION,
            channel=COPY_LINKEDIN_CHANNEL,
        )
    else:
        instruction = COPY_LINKEDIN_BASE_INSTRUCTION

    return Agent(
        name=COPY_LINKEDIN_NAME,
        description=COPY_LINKEDIN_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=2048,
        ),
    )


copy_linkedin_agent = build_copy_linkedin_agent()
