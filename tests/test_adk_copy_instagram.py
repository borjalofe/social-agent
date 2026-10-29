"""ADK copy_instagram specialist wiring (no live LLM calls)."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents import (
    InstructionProvider,
    build_copy_instagram_agent,
    build_root_agent,
    copy_instagram_agent,
    root_agent,
)
from social_agent.agents.copy_instagram import (
    COPY_INSTAGRAM_BASE_INSTRUCTION,
    COPY_INSTAGRAM_CHANNEL,
    COPY_INSTAGRAM_NAME,
)
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.voice import InMemoryVoiceStore


def test_module_copy_instagram_is_draft_only_specialist() -> None:
    assert copy_instagram_agent.name == COPY_INSTAGRAM_NAME
    assert copy_instagram_agent.tools == []
    assert "publish" in COPY_INSTAGRAM_BASE_INSTRUCTION.lower()
    assert "draft" in COPY_INSTAGRAM_BASE_INSTRUCTION.lower()
    assert "caption" in COPY_INSTAGRAM_BASE_INSTRUCTION.lower()
    assert copy_instagram_agent.instruction == COPY_INSTAGRAM_BASE_INSTRUCTION


def test_root_agent_registers_five_channels_and_instagram() -> None:
    names = [agent.name for agent in root_agent.sub_agents]
    assert names[0] == "copy_linkedin"
    assert names[1] == "copy_x"
    assert names[2] == "copy_blog"
    assert names[3] == "copy_medium"
    assert names[4] == "copy_youtube"
    assert names[5] == COPY_INSTAGRAM_NAME
    assert COPY_INSTAGRAM_NAME in names


def test_build_copy_instagram_with_instruction_provider() -> None:
    user_id = uuid.uuid4()
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    voice.put(user_id, "tono cercano")
    canal.create(user_id, channel=COPY_INSTAGRAM_CHANNEL, body="hook + CTA")
    provider = InstructionProvider(
        voice_store=voice,
        context_store=context,
        canal_rule_store=canal,
    )
    agent = build_copy_instagram_agent(model="test-model", instruction_provider=provider)
    assert agent.name == COPY_INSTAGRAM_NAME
    assert agent.model == "test-model"
    assert callable(agent.instruction)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({}),
    )
    packed = agent.instruction(ctx)  # type: ignore[misc, operator]
    assert "tono cercano" in packed
    assert f"## Channel rules ({COPY_INSTAGRAM_CHANNEL})\nhook + CTA" in packed
    assert "Do not publish" in packed or "do not publish" in packed.lower()


def test_build_root_agent_can_include_copy_instagram_only() -> None:
    router = build_root_agent(
        model="test-model",
        sub_agents=[build_copy_instagram_agent(model="test-model")],
    )
    assert [a.name for a in router.sub_agents] == [COPY_INSTAGRAM_NAME]
