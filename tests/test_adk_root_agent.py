"""ADK root_agent router wiring (no live LLM calls)."""

from __future__ import annotations

import pytest
from google.adk.agents import Agent

from social_agent.agents import (
    DEFAULT_ROOT_MODEL,
    ROOT_AGENT_NAME,
    build_root_agent,
    root_agent,
)
from social_agent.agents.root_agent import ROOT_AGENT_DESCRIPTION, ROOT_AGENT_INSTRUCTION


def test_module_root_agent_is_router_with_default_specialists() -> None:
    assert root_agent.name == ROOT_AGENT_NAME
    assert root_agent.description == ROOT_AGENT_DESCRIPTION
    assert root_agent.instruction == ROOT_AGENT_INSTRUCTION
    assert root_agent.model == DEFAULT_ROOT_MODEL
    assert [agent.name for agent in root_agent.sub_agents] == [
        "copy_linkedin",
        "copy_x",
        "copy_blog",
        "copy_medium",
        "copy_youtube",
        "copy_instagram",
    ]
    assert "route" in ROOT_AGENT_INSTRUCTION.lower() or "Routes" in ROOT_AGENT_DESCRIPTION
    assert "do not write" in ROOT_AGENT_INSTRUCTION.lower()


def test_build_root_agent_empty_sub_agents_clears_defaults() -> None:
    assert build_root_agent(sub_agents=[]).sub_agents == []


def test_build_root_agent_registers_specialists() -> None:
    specialist = Agent(
        name="copy_linkedin",
        description="LinkedIn copy specialist (stub for wiring test).",
        instruction="Write LinkedIn posts.",
        model="test-model",
    )
    router = build_root_agent(model="test-model", sub_agents=[specialist])
    assert router.name == ROOT_AGENT_NAME
    assert router.model == "test-model"
    assert [agent.name for agent in router.sub_agents] == ["copy_linkedin"]


def test_build_root_agent_model_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_AGENT_ROOT_MODEL", "ollama_chat/gemma3:1b")
    router = build_root_agent()
    assert router.model == "ollama_chat/gemma3:1b"
