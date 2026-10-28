"""ADK copy_x specialist wiring (no live LLM calls)."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents import (
    InstructionProvider,
    build_copy_x_agent,
    build_root_agent,
    copy_x_agent,
    root_agent,
)
from social_agent.agents.copy_x import (
    COPY_X_BASE_INSTRUCTION,
    COPY_X_CHANNEL,
    COPY_X_NAME,
)
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.voice import InMemoryVoiceStore


def test_module_copy_x_is_draft_only_specialist() -> None:
    assert copy_x_agent.name == COPY_X_NAME
    assert copy_x_agent.tools == []
    assert "publish" in COPY_X_BASE_INSTRUCTION.lower()
    assert "draft" in COPY_X_BASE_INSTRUCTION.lower()
    assert "280" in COPY_X_BASE_INSTRUCTION
    assert copy_x_agent.instruction == COPY_X_BASE_INSTRUCTION


def test_root_agent_registers_copy_linkedin_and_copy_x() -> None:
    names = [agent.name for agent in root_agent.sub_agents]
    assert names[0] == "copy_linkedin"
    assert names[1] == COPY_X_NAME
    assert COPY_X_NAME in names


def test_build_copy_x_with_instruction_provider() -> None:
    user_id = uuid.uuid4()
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    voice.put(user_id, "tono directo")
    canal.create(user_id, channel=COPY_X_CHANNEL, body="un tip + link")
    provider = InstructionProvider(
        voice_store=voice,
        context_store=context,
        canal_rule_store=canal,
    )
    agent = build_copy_x_agent(model="test-model", instruction_provider=provider)
    assert agent.name == COPY_X_NAME
    assert agent.model == "test-model"
    assert callable(agent.instruction)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({}),
    )
    packed = agent.instruction(ctx)  # type: ignore[misc, operator]
    assert "tono directo" in packed
    assert f"## Channel rules ({COPY_X_CHANNEL})\nun tip + link" in packed
    assert "Do not publish" in packed or "do not publish" in packed.lower()


def test_build_root_agent_can_include_copy_x_only() -> None:
    router = build_root_agent(
        model="test-model",
        sub_agents=[build_copy_x_agent(model="test-model")],
    )
    assert [a.name for a in router.sub_agents] == [COPY_X_NAME]
