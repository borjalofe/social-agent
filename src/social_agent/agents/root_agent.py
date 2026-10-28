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
- Prefer the specialist whose name matches the channel or task
  (e.g. copy_linkedin, copy_x).
- Keep replies short when you cannot transfer.
"""


def _resolve_model(model: str | Any | None) -> str | Any:
    if model is not None:
        return model
    return os.environ.get("SOCIAL_AGENT_ROOT_MODEL", DEFAULT_ROOT_MODEL)


def _default_sub_agents(*, model: str | Any | None = None) -> list[BaseAgent]:
    # Late imports avoid cycles with specialists (they do not import root).
    from social_agent.agents.copy_linkedin import build_copy_linkedin_agent
    from social_agent.agents.copy_x import build_copy_x_agent

    return [
        build_copy_linkedin_agent(model=model),
        build_copy_x_agent(model=model),
    ]


def build_root_agent(
    *,
    model: str | Any | None = None,
    sub_agents: Sequence[BaseAgent] | None = None,
) -> Agent:
    """Build the ADK root router.

    Default specialists: `copy_linkedin`, `copy_x`. Pass `sub_agents=[]` to clear.
    """
    resolved = list(sub_agents) if sub_agents is not None else _default_sub_agents(model=model)
    return Agent(
        name=ROOT_AGENT_NAME,
        description=ROOT_AGENT_DESCRIPTION,
        instruction=ROOT_AGENT_INSTRUCTION,
        model=_resolve_model(model),
        sub_agents=resolved,
        generate_content_config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=512,
        ),
    )


# Default export for ADK discovery (includes copy_linkedin + copy_x).
root_agent = build_root_agent()
