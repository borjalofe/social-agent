"""ADK copy_blog specialist wiring (no live LLM calls)."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents import (
    InstructionProvider,
    build_copy_blog_agent,
    build_root_agent,
    copy_blog_agent,
    root_agent,
)
from social_agent.agents.copy_blog import (
    COPY_BLOG_BASE_INSTRUCTION,
    COPY_BLOG_CHANNEL,
    COPY_BLOG_NAME,
)
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.voice import InMemoryVoiceStore


def test_module_copy_blog_is_draft_only_specialist() -> None:
    assert copy_blog_agent.name == COPY_BLOG_NAME
    assert copy_blog_agent.tools == []
    assert "publish" in COPY_BLOG_BASE_INSTRUCTION.lower()
    assert "draft" in COPY_BLOG_BASE_INSTRUCTION.lower()
    assert "markdown" in COPY_BLOG_BASE_INSTRUCTION.lower()
    assert copy_blog_agent.instruction == COPY_BLOG_BASE_INSTRUCTION


def test_root_agent_registers_linkedin_x_and_blog() -> None:
    assert [agent.name for agent in root_agent.sub_agents] == [
        "copy_linkedin",
        "copy_x",
        COPY_BLOG_NAME,
    ]


def test_build_copy_blog_with_instruction_provider() -> None:
    user_id = uuid.uuid4()
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    voice.put(user_id, "tono técnico claro")
    canal.create(user_id, channel=COPY_BLOG_CHANNEL, body="titulo + secciones cortas")
    provider = InstructionProvider(
        voice_store=voice,
        context_store=context,
        canal_rule_store=canal,
    )
    agent = build_copy_blog_agent(model="test-model", instruction_provider=provider)
    assert agent.name == COPY_BLOG_NAME
    assert agent.model == "test-model"
    assert callable(agent.instruction)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({}),
    )
    packed = agent.instruction(ctx)  # type: ignore[misc, operator]
    assert "tono técnico claro" in packed
    assert f"## Channel rules ({COPY_BLOG_CHANNEL})\ntitulo + secciones cortas" in packed
    assert "Do not publish" in packed or "do not publish" in packed.lower()


def test_build_root_agent_can_include_copy_blog_only() -> None:
    router = build_root_agent(
        model="test-model",
        sub_agents=[build_copy_blog_agent(model="test-model")],
    )
    assert [a.name for a in router.sub_agents] == [COPY_BLOG_NAME]
