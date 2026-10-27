# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-10-27

First M2 MVP slice after ADK `copy_linkedin`: Siren API + auth + session stores + LinkedIn draft specialist.

### Added

- PostgreSQL schemas via Alembic: `users`, `voice_docs`, `context_docs`, `canal_rules`, `social_accounts`, `llm_connections`, `publications`, `agent_sessions`
- Redis `AgentSessionPayloadStore` for agent session payloads
- JWT authn (access + rotating refresh) and Siren action authz (owner-only)
- Siren resources: `home`, `user`, `voice`, `context`, `canal-rules`, `social-accounts`, `llm-connections`, `publications`, `agent-run`
- Publication lifecycle lock (`scheduled` / `published` → no edit)
- Fernet sealing for social-account and LLM credentials (redacted in Siren)
- ADK `root_agent` router, `InstructionProvider` (voice/context/canal-rules packs), `copy_linkedin` draft specialist
- CI quality gates and daily audit workflow

### Security

- Credentials never appear in Siren properties or InstructionProvider packs
- `copy_linkedin` is draft-only (no publish tools)
- `opentelemetry-api` forced to ≥1.45.1 (CVE-2026-114603) while google-adk pins ≤1.44

### Announcement

- Blog (canonical content repo): [EN](https://github.com/borjalofe/blog/blob/main/content/posts/en/social-agent-0-1-0.md) · [ES](https://github.com/borjalofe/blog/blob/main/content/posts/es/social-agent-0-1-0.md)
- Network drafts live as vault `Publication` notes (LinkedIn / X / Medium); public URLs land when those posts ship

### Audit

- Post-release audit 2026-10-27: SCA/SAST clean; no `[FIX]` / PATCH — [docs/audits/0.1.0.md](docs/audits/0.1.0.md)

[0.1.0]: https://github.com/borjalofe/social-agent/releases/tag/0.1.0
