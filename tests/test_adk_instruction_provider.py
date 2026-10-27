"""InstructionProvider packs voice/context/canal-rules without secrets."""

from __future__ import annotations

import uuid
from types import MappingProxyType, SimpleNamespace

from social_agent.agents.instruction_provider import InstructionProvider
from social_agent.siren.canal_rules import InMemoryCanalRuleStore
from social_agent.siren.context import InMemoryContextStore
from social_agent.siren.voice import InMemoryVoiceStore


def _provider() -> tuple[
    InstructionProvider,
    InMemoryVoiceStore,
    InMemoryContextStore,
    InMemoryCanalRuleStore,
]:
    voice = InMemoryVoiceStore()
    context = InMemoryContextStore()
    canal = InMemoryCanalRuleStore()
    return (
        InstructionProvider(
            voice_store=voice,
            context_store=context,
            canal_rule_store=canal,
        ),
        voice,
        context,
        canal,
    )


def test_pack_empty_user_returns_none_sections() -> None:
    provider, _, _, _ = _provider()
    user_id = uuid.uuid4()
    packed = provider.pack(user_id, base_instruction="Write LinkedIn copy.")
    assert packed.startswith("Write LinkedIn copy.")
    assert "## Editorial voice\n(none)" in packed
    assert "## Context\n(none)" in packed
    assert "## Channel rules\n(none)" in packed


def test_pack_includes_voice_context_and_channel_rule() -> None:
    provider, voice, context, canal = _provider()
    user_id = uuid.uuid4()
    voice.put(user_id, "tono directo, sin marketing")
    context.create(user_id, title="Marca", body="seguridad × IA")
    canal.create(user_id, channel="linkedin", body="hooks cortos")
    canal.create(user_id, channel="x", body="280 chars")

    packed = provider.pack(
        user_id,
        channel="linkedin",
        base_instruction="Specialist: copy_linkedin",
    )
    assert "Specialist: copy_linkedin" in packed
    assert "tono directo, sin marketing" in packed
    assert "### Marca\nseguridad × IA" in packed
    assert "## Channel rules (linkedin)\nhooks cortos" in packed
    assert "280 chars" not in packed


def test_pack_lists_all_canal_rules_without_channel() -> None:
    provider, _, _, canal = _provider()
    user_id = uuid.uuid4()
    canal.create(user_id, channel="linkedin", body="LI")
    canal.create(user_id, channel="x", body="X")
    packed = provider.pack(user_id)
    assert "### linkedin\nLI" in packed
    assert "### x\nX" in packed


def test_pack_is_scoped_to_user() -> None:
    provider, voice, context, canal = _provider()
    a = uuid.uuid4()
    b = uuid.uuid4()
    voice.put(a, "voz A")
    voice.put(b, "voz B")
    context.create(a, title="A", body="solo A")
    canal.create(a, channel="linkedin", body="reglas A")
    packed = provider.pack(b, channel="linkedin")
    assert "voz B" in packed
    assert "voz A" not in packed
    assert "solo A" not in packed
    assert "reglas A" not in packed
    assert "## Channel rules (linkedin)\n(none)" in packed


def test_for_agent_callable_uses_ctx_user_and_state_channel() -> None:
    provider, voice, _, canal = _provider()
    user_id = uuid.uuid4()
    voice.put(user_id, "voz ctx")
    canal.create(user_id, channel="linkedin", body="reglas LI")
    instruction = provider.for_agent("Base.", channel=None)

    ctx = SimpleNamespace(
        user_id=str(user_id),
        state=MappingProxyType({"channel": "linkedin"}),
    )
    text = instruction(ctx)  # type: ignore[arg-type]
    assert "Base." in text
    assert "voz ctx" in text
    assert "## Channel rules (linkedin)\nreglas LI" in text


def test_for_agent_invalid_user_id_returns_base_only() -> None:
    provider, _, _, _ = _provider()
    instruction = provider.for_agent("Base only.")
    ctx = SimpleNamespace(user_id="not-a-uuid", state=MappingProxyType({}))
    assert instruction(ctx) == "Base only.\n"  # type: ignore[arg-type]
