"""ADK `copy_x` specialist: draft X (Twitter) copy only (no publish/approve)."""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import Agent
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider

COPY_X_NAME = "copy_x"
COPY_X_CHANNEL = "x"
DEFAULT_COPY_X_MODEL = "gemini-2.0-flash"

COPY_X_DESCRIPTION = "Drafts X (Twitter) posts in the user's voice; does not publish or approve."

COPY_X_BASE_INSTRUCTION = """\
You are the Social Agent X/Twitter copy specialist (`copy_x`).

Responsibilities:
- Draft posts for X that match the editorial voice, context, and channel rules below.
- Return draft copy only. Do not publish, schedule, or call external APIs.
- Do not invent credentials, approvals, or facts absent from the brief / context.

X craft:
- One concrete detail or punch; link out when the rest lives on the blog.
- Prefer a single post under ~280 characters unless the brief asks for a short thread.
- No endless threads. No employment-funnel tone (that stays on LinkedIn).
- Follow channel rules when present; if voice/context is "(none)", ask for what's missing
  instead of inventing a brand voice.

Security:
- Least privilege: draft text only. Never request or echo secrets.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_COPY_X_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_COPY_X_MODEL),
    )


def build_copy_x_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
) -> Agent:
    """Build the X specialist. Inject InstructionProvider for per-user packs."""
    instruction: str | InstructionFn
    if instruction_provider is not None:
        instruction = instruction_provider.for_agent(
            COPY_X_BASE_INSTRUCTION,
            channel=COPY_X_CHANNEL,
        )
    else:
        instruction = COPY_X_BASE_INSTRUCTION

    return Agent(
        name=COPY_X_NAME,
        description=COPY_X_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=1024,
        ),
    )


copy_x_agent = build_copy_x_agent()
