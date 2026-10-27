"""Siren hypermedia resources."""

from social_agent.siren.canal_rules import (
    EXPECTED_CANAL_RULES_COLLECTION_RELS,
    CanalRuleRecord,
    InMemoryCanalRuleStore,
    build_canal_rule_item,
    build_canal_rules_collection,
)
from social_agent.siren.context import (
    EXPECTED_CONTEXT_COLLECTION_RELS,
    ContextRecord,
    InMemoryContextStore,
    build_context_collection,
    build_context_item,
)
from social_agent.siren.home import EXPECTED_HOME_RELS, SIREN_MEDIA_TYPE, build_home
from social_agent.siren.llm_connections import (
    EXPECTED_LLM_CONNECTIONS_COLLECTION_RELS,
    InMemoryLlmConnectionStore,
    LlmConnectionRecord,
    build_llm_connection_item,
    build_llm_connections_collection,
)
from social_agent.siren.publications import (
    EXPECTED_PUBLICATIONS_COLLECTION_RELS,
    InMemoryPublicationStore,
    PublicationRecord,
    build_publication_item,
    build_publications_collection,
)
from social_agent.siren.social_accounts import (
    EXPECTED_SOCIAL_ACCOUNTS_COLLECTION_RELS,
    InMemorySocialAccountStore,
    SocialAccountRecord,
    build_social_account_item,
    build_social_accounts_collection,
)
from social_agent.siren.user import EXPECTED_USER_RELS, build_user
from social_agent.siren.voice import (
    EXPECTED_VOICE_RELS,
    InMemoryVoiceStore,
    VoiceRecord,
    build_voice,
)

__all__ = [
    "EXPECTED_CANAL_RULES_COLLECTION_RELS",
    "EXPECTED_CONTEXT_COLLECTION_RELS",
    "EXPECTED_HOME_RELS",
    "EXPECTED_LLM_CONNECTIONS_COLLECTION_RELS",
    "EXPECTED_PUBLICATIONS_COLLECTION_RELS",
    "EXPECTED_SOCIAL_ACCOUNTS_COLLECTION_RELS",
    "EXPECTED_USER_RELS",
    "EXPECTED_VOICE_RELS",
    "CanalRuleRecord",
    "ContextRecord",
    "InMemoryCanalRuleStore",
    "InMemoryContextStore",
    "InMemoryLlmConnectionStore",
    "InMemoryPublicationStore",
    "InMemorySocialAccountStore",
    "InMemoryVoiceStore",
    "LlmConnectionRecord",
    "PublicationRecord",
    "SIREN_MEDIA_TYPE",
    "SocialAccountRecord",
    "VoiceRecord",
    "build_canal_rule_item",
    "build_canal_rules_collection",
    "build_context_collection",
    "build_context_item",
    "build_home",
    "build_llm_connection_item",
    "build_llm_connections_collection",
    "build_publication_item",
    "build_publications_collection",
    "build_social_account_item",
    "build_social_accounts_collection",
    "build_user",
    "build_voice",
]
