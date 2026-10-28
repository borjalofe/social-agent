"""ADK copy_linkedin specialist wiring (no live LLM calls)."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents import (
    InstructionProvider,
    build_copy_linkedin_agent,
    build_root_agent,
    copy_linkedin_agent,
    root_agent,
)
from social_agent.agents.copy_linkedin import (
    COPY_LINKEDIN_BASE_INSTRUCTION,
    COPY_LINKEDIN_CHANNEL,
    COPY_LINKEDIN_NAME,
)
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.voice import InMemoryVoiceStore


def test_module_copy_linkedin_is_draft_only_specialist() -> None:
    assert copy_linkedin_agent.name == COPY_LINKEDIN_NAME
    assert copy_linkedin_agent.tools == []
    assert "publish" in COPY_LINKEDIN_BASE_INSTRUCTION.lower()
    assert "draft" in COPY_LINKEDIN_BASE_INSTRUCTION.lower()
    assert copy_linkedin_agent.instruction == COPY_LINKEDIN_BASE_INSTRUCTION


def test_root_agent_registers_copy_linkedin_by_default() -> None:
    names = [agent.name for agent in root_agent.sub_agents]
    assert COPY_LINKEDIN_NAME in names
    assert names[0] == COPY_LINKEDIN_NAME


def test_build_copy_linkedin_with_instruction_provider() -> None:
    user_id = uuid.uuid4()
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    voice.put(user_id, "tono directo")
    canal.create(user_id, channel=COPY_LINKEDIN_CHANNEL, body="hooks cortos")
    provider = InstructionProvider(
        voice_store=voice,
        context_store=context,
        canal_rule_store=canal,
    )
    agent = build_copy_linkedin_agent(model="test-model", instruction_provider=provider)
    assert agent.name == COPY_LINKEDIN_NAME
    assert agent.model == "test-model"
    assert callable(agent.instruction)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({}),
    )
    packed = agent.instruction(ctx)  # type: ignore[misc, operator]
    assert "tono directo" in packed
    assert f"## Channel rules ({COPY_LINKEDIN_CHANNEL})\nhooks cortos" in packed
    assert "Do not publish" in packed or "do not publish" in packed.lower()


def test_build_root_agent_can_override_specialists() -> None:
    router = build_root_agent(model="test-model", sub_agents=[])
    assert router.sub_agents == []
    with_specialist = build_root_agent(
        model="test-model",
        sub_agents=[build_copy_linkedin_agent(model="test-model")],
    )
    assert [a.name for a in with_specialist.sub_agents] == [COPY_LINKEDIN_NAME]
