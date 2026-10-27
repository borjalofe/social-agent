"""ADK agents (swarm: root router + specialists in later PRs)."""

from social_agent.agents.instruction_provider import InstructionProvider
from social_agent.agents.root_agent import (
    DEFAULT_ROOT_MODEL,
    ROOT_AGENT_NAME,
    build_root_agent,
    root_agent,
)

__all__ = [
    "DEFAULT_ROOT_MODEL",
    "InstructionProvider",
    "ROOT_AGENT_NAME",
    "build_root_agent",
    "root_agent",
]
