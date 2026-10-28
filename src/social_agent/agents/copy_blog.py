"""ADK `copy_blog` specialist: draft long-form blog copy only (no publish/approve)."""

from __future__ import annotations

import os
from typing import Any

from google.adk.agents import Agent
from google.genai import types

from social_agent.agents.instruction_provider import InstructionFn, InstructionProvider

COPY_BLOG_NAME = "copy_blog"
COPY_BLOG_CHANNEL = "blog"
DEFAULT_COPY_BLOG_MODEL = "gemini-2.0-flash"

COPY_BLOG_DESCRIPTION = (
    "Drafts long-form blog posts in the user's voice; does not publish or approve."
)

COPY_BLOG_BASE_INSTRUCTION = """\
You are the Social Agent blog copy specialist (`copy_blog`).

Responsibilities:
- Draft long-form blog posts that match the editorial voice, context, and channel rules below.
- Return draft copy only. Do not publish, schedule, or call external APIs.
- Do not invent credentials, approvals, or facts absent from the brief / context.

Blog craft:
- Clear title + short description/lede, then Markdown body with short sections.
- One primary idea; concrete detail over hype. Prefer bilingual-ready structure when asked.
- No employment-funnel tone (that stays on LinkedIn); no tweet-length punch-only (that stays on X).
- Follow channel rules when present; if voice/context is "(none)", ask for what's missing
  instead of inventing a brand voice.

Security:
- Least privilege: draft text only. Never request or echo secrets.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get(
        "SOCIAL_AGENT_COPY_BLOG_MODEL",
        os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_COPY_BLOG_MODEL),
    )


def build_copy_blog_agent(
    *,
    model: str | Any | None = None,
    instruction_provider: InstructionProvider | None = None,
) -> Agent:
    """Build the blog specialist. Inject InstructionProvider for per-user packs."""
    instruction: str | InstructionFn
    if instruction_provider is not None:
        instruction = instruction_provider.for_agent(
            COPY_BLOG_BASE_INSTRUCTION,
            channel=COPY_BLOG_CHANNEL,
        )
    else:
        instruction = COPY_BLOG_BASE_INSTRUCTION

    return Agent(
        name=COPY_BLOG_NAME,
        description=COPY_BLOG_DESCRIPTION,
        instruction=instruction,
        model=_resolve_model(model),
        tools=[],
        generate_content_config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=4096,
        ),
    )


copy_blog_agent = build_copy_blog_agent()
