"""ADK agents (swarm: root router + channel specialists)."""

from social_agent.agents.copy_blog import (
    COPY_BLOG_NAME,
    build_copy_blog_agent,
    copy_blog_agent,
)
from social_agent.agents.copy_linkedin import (
    COPY_LINKEDIN_NAME,
    build_copy_linkedin_agent,
    copy_linkedin_agent,
)
from social_agent.agents.copy_medium import (
    COPY_MEDIUM_NAME,
    build_copy_medium_agent,
    copy_medium_agent,
)
from social_agent.agents.copy_x import COPY_X_NAME, build_copy_x_agent, copy_x_agent
from social_agent.agents.instruction_provider import InstructionProvider
from social_agent.agents.root_agent import (
    DEFAULT_ROOT_MODEL,
    ROOT_AGENT_NAME,
    build_root_agent,
    root_agent,
)

__all__ = [
    "COPY_BLOG_NAME",
    "COPY_LINKEDIN_NAME",
    "COPY_MEDIUM_NAME",
    "COPY_X_NAME",
    "DEFAULT_ROOT_MODEL",
    "InstructionProvider",
    "ROOT_AGENT_NAME",
    "build_copy_blog_agent",
    "build_copy_linkedin_agent",
    "build_copy_medium_agent",
    "build_copy_x_agent",
    "build_root_agent",
    "copy_blog_agent",
    "copy_linkedin_agent",
    "copy_medium_agent",
    "copy_x_agent",
    "root_agent",
]
