"""ADK copy_youtube specialist wiring (no live LLM calls)."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents import (
    InstructionProvider,
    build_copy_youtube_agent,
    build_root_agent,
    copy_youtube_agent,
    root_agent,
)
from social_agent.agents.copy_youtube import (
    COPY_YOUTUBE_BASE_INSTRUCTION,
    COPY_YOUTUBE_CHANNEL,
    COPY_YOUTUBE_NAME,
)
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.voice import InMemoryVoiceStore


def test_module_copy_youtube_is_draft_only_specialist() -> None:
    assert copy_youtube_agent.name == COPY_YOUTUBE_NAME
    assert copy_youtube_agent.tools == []
    assert "publish" in COPY_YOUTUBE_BASE_INSTRUCTION.lower()
    assert "draft" in COPY_YOUTUBE_BASE_INSTRUCTION.lower()
    assert "script" in COPY_YOUTUBE_BASE_INSTRUCTION.lower()
    assert copy_youtube_agent.instruction == COPY_YOUTUBE_BASE_INSTRUCTION


def test_root_agent_registers_four_channels_and_youtube() -> None:
    assert [agent.name for agent in root_agent.sub_agents] == [
        "copy_linkedin",
        "copy_x",
        "copy_blog",
        "copy_medium",
        COPY_YOUTUBE_NAME,
    ]


def test_build_copy_youtube_with_instruction_provider() -> None:
    user_id = uuid.uuid4()
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    voice.put(user_id, "tono didáctico")
    canal.create(user_id, channel=COPY_YOUTUBE_CHANNEL, body="hook + capítulos")
    provider = InstructionProvider(
        voice_store=voice,
        context_store=context,
        canal_rule_store=canal,
    )
    agent = build_copy_youtube_agent(model="test-model", instruction_provider=provider)
    assert agent.name == COPY_YOUTUBE_NAME
    assert agent.model == "test-model"
    assert callable(agent.instruction)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({}),
    )
    packed = agent.instruction(ctx)  # type: ignore[misc, operator]
    assert "tono didáctico" in packed
    assert f"## Channel rules ({COPY_YOUTUBE_CHANNEL})\nhook + capítulos" in packed
    assert "Do not publish" in packed or "do not publish" in packed.lower()


def test_build_root_agent_can_include_copy_youtube_only() -> None:
    router = build_root_agent(
        model="test-model",
        sub_agents=[build_copy_youtube_agent(model="test-model")],
    )
    assert [a.name for a in router.sub_agents] == [COPY_YOUTUBE_NAME]
