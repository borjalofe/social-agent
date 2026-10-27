"""ADK `root_agent`: router only (delegates to specialist sub-agents)."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from google.adk.agents import Agent
from google.adk.agents.base_agent import BaseAgent
from google.genai import types

ROOT_AGENT_NAME = "root_agent"

# Placeholder until compose / llm-connections wire a real backend.
DEFAULT_ROOT_MODEL = "gemini-2.0-flash"

ROOT_AGENT_DESCRIPTION = (
    "Routes editorial requests to specialist sub-agents; does not write channel copy."
)

ROOT_AGENT_INSTRUCTION = """\
You are the Social Agent root router.

Responsibilities:
- Decide which specialist sub-agent should handle the user request.
- Transfer to that sub-agent by name. Do not write LinkedIn/X/blog/etc. copy yourself.
- If no registered sub-agent matches, say briefly that the specialist is unavailable.

Rules:
- Least privilege: only route; never invent credentials, publishes, or approvals.
- Prefer the specialist whose name matches the channel or task (e.g. copy_linkedin).
- Keep replies short when you cannot transfer.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_ROOT_MODEL)


def build_root_agent(
    *,
    model: str | Any | None = None,
    sub_agents: Sequence[BaseAgent] | None = None,
) -> Agent:
    """Build the ADK root router. Inject specialists later (e.g. copy_linkedin)."""
    return Agent(
        name=ROOT_AGENT_NAME,
        description=ROOT_AGENT_DESCRIPTION,
        instruction=ROOT_AGENT_INSTRUCTION,
        model=_resolve_model(model),
        sub_agents=list(sub_agents or ()),
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=512,
        ),
    )


# Default export for ADK discovery; specialists register via build_root_agent(...).
root_agent = build_root_agent()
