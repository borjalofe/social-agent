"""Pack voice / context / canal-rules into ADK agent instructions (no secrets)."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from google.adk.agents.readonly_context import ReadonlyContext

from social_agent.siren.canal_rules import CanalRuleStore
from social_agent.siren.context import ContextStore
from social_agent.siren.voice import VoiceStore

InstructionFn = Callable[[ReadonlyContext], str]


class InstructionProvider:
    """Build per-user editorial instruction packs from injectable stores.

    Never includes credentials (social accounts / LLM keys stay out of prompts).
    """

    def __init__(
        self,
        *,
        voice_store: VoiceStore,
        context_store: ContextStore,
        canal_rule_store: CanalRuleStore,
    ) -> None:
        self._voice = voice_store
        self._context = context_store
        self._canal_rules = canal_rule_store

    def pack(
        self,
        user_id: uuid.UUID,
        *,
        channel: str | None = None,
        base_instruction: str = "",
    ) -> str:
        """Assemble base + voice + context docs + canal rules for one user."""
        sections: list[str] = []
        base = base_instruction.strip()
        if base:
            sections.append(base)

        voice = self._voice.get(user_id)
        voice_body = voice.body.strip() if voice is not None else ""
        sections.append("## Editorial voice\n" + (voice_body if voice_body else "(none)"))

        docs = self._context.list(user_id)
        if not docs:
            sections.append("## Context\n(none)")
        else:
            chunks = ["## Context"]
            for doc in docs:
                chunks.append(f"### {doc.title}\n{doc.body}".rstrip())
            sections.append("\n\n".join(chunks))

        if channel is not None:
            rule = self._canal_rules.get(user_id, channel)
            body = rule.body.strip() if rule is not None else ""
            sections.append(f"## Channel rules ({channel})\n" + (body if body else "(none)"))
        else:
            rules = self._canal_rules.list(user_id)
            if not rules:
                sections.append("## Channel rules\n(none)")
            else:
                chunks = ["## Channel rules"]
                for rule in rules:
                    chunks.append(f"### {rule.channel}\n{rule.body}".rstrip())
                sections.append("\n\n".join(chunks))

        return "\n\n".join(sections).rstrip() + "\n"

    def for_agent(
        self,
        base_instruction: str = "",
        *,
        channel: str | None = None,
    ) -> InstructionFn:
        """ADK `instruction=` callable: packs from `ctx.user_id` (+ optional state channel)."""

        def _instruction(ctx: ReadonlyContext) -> str:
            try:
                user_id = uuid.UUID(str(ctx.user_id))
            except (TypeError, ValueError):
                return base_instruction.strip() + ("\n" if base_instruction.strip() else "")

            resolved_channel = channel
            if resolved_channel is None:
                state_channel = ctx.state.get("channel")
                if isinstance(state_channel, str) and state_channel.strip():
                    resolved_channel = state_channel.strip()

            return self.pack(
                user_id,
                channel=resolved_channel,
                base_instruction=base_instruction,
            )

        return _instruction
