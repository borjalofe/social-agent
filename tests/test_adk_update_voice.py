"""ADK update_voice specialist wiring (no live LLM calls)."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents import (
    InstructionProvider,
    build_root_agent,
    build_update_voice_agent,
    root_agent,
    update_voice_agent,
)
from social_agent.agents.update_voice import (
    UPDATE_VOICE_BASE_INSTRUCTION,
    UPDATE_VOICE_NAME,
    format_publications_corpus,
)
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.publications import InMemoryPublicationStore
from social_agent.siren.voice import InMemoryVoiceStore


def test_module_update_voice_is_draft_only_specialist() -> None:
    assert update_voice_agent.name == UPDATE_VOICE_NAME
    assert update_voice_agent.tools == []
    assert "publish" in UPDATE_VOICE_BASE_INSTRUCTION.lower()
    assert "draft" in UPDATE_VOICE_BASE_INSTRUCTION.lower()
    assert "corpus" in UPDATE_VOICE_BASE_INSTRUCTION.lower()
    assert "network" in UPDATE_VOICE_BASE_INSTRUCTION.lower()
    assert update_voice_agent.instruction == UPDATE_VOICE_BASE_INSTRUCTION


def test_root_agent_registers_update_voice() -> None:
    names = [agent.name for agent in root_agent.sub_agents]
    assert UPDATE_VOICE_NAME in names
    assert names[-1] == UPDATE_VOICE_NAME


def test_format_publications_corpus_empty() -> None:
    assert format_publications_corpus([]) == "## Publications corpus\n(none)\n"


def test_build_update_voice_packs_voice_and_publications() -> None:
    user_id = uuid.uuid4()
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    pubs = InMemoryPublicationStore()
    voice.put(user_id, "tono seco")
    pubs.create(
        user_id,
        channel="linkedin",
        title="Homelab",
        body="Ya conte que el router importa.",
        status="approved",
        scheduled_at=None,
        published_at=None,
    )
    provider = InstructionProvider(
        voice_store=voice,
        context_store=context,
        canal_rule_store=canal,
    )
    agent = build_update_voice_agent(
        model="test-model",
        instruction_provider=provider,
        publication_store=pubs,
    )
    assert agent.name == UPDATE_VOICE_NAME
    assert agent.model == "test-model"
    assert callable(agent.instruction)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({}),
    )
    packed = agent.instruction(ctx)  # type: ignore[misc, operator]
    assert "tono seco" in packed
    assert "## Publications corpus" in packed
    assert "Ya conte que el router importa." in packed
    assert "Homelab" in packed
    assert "Do not publish" in packed or "do not publish" in packed.lower()
    assert "Do not write network" in packed or "network copy" in packed.lower()


def test_build_root_agent_can_include_update_voice_only() -> None:
    router = build_root_agent(
        model="test-model",
        sub_agents=[build_update_voice_agent(model="test-model")],
    )
    assert [a.name for a in router.sub_agents] == [UPDATE_VOICE_NAME]
