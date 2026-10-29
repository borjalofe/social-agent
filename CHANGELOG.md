# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-10-28

Third M2 channel slice: ADK `copy_blog` under `root_agent` with LinkedIn and X.

### Added

- ADK `copy_blog` draft specialist (InstructionProvider channel `blog`); Markdown title/lede/body; registered under `root_agent` with `copy_linkedin` and `copy_x`
- `.env.example` `SOCIAL_AGENT_COPY_BLOG_MODEL`

### Security

- `copy_blog` is draft-only (`tools=[]`); no publish/approve tools

### Announcement

- Blog (canonical content repo): [EN](https://github.com/borjalofe/blog/blob/main/content/posts/en/social-agent-0-3-0.md) · [ES](https://github.com/borjalofe/blog/blob/main/content/posts/es/social-agent-0-3-0.md)
- Network drafts live as vault `Publication` notes (LinkedIn / X / Medium); public URLs land when those posts ship

### Audit

- Post-release audit 2026-10-29: SCA/SAST clean; no `[FIX]` / PATCH — [docs/audits/0.3.0.md](docs/audits/0.3.0.md)

[0.3.0]: https://github.com/borjalofe/social-agent/releases/tag/0.3.0

## [0.2.0] — 2026-10-28

Second M2 channel slice: ADK `copy_x`, approve-draft → calendar, and local Compose runtime.

### Added

- ADK `copy_x` draft specialist (InstructionProvider channel `x`); registered under `root_agent` with `copy_linkedin`
- `POST /agent-run/{id}/approve` — persist `payload.draft` as an `approved` publication; mark run `completed`
- Local runtime: `compose.yaml` (Postgres 16 + Redis 7 + API), `Dockerfile`, `.env.example` (JWT / Fernet / Claude), `create_app_from_env`

### Security

- `copy_x` is draft-only (`tools=[]`); approve remains owner-scoped via JWT + authz

### Announcement

- Blog (canonical content repo): [EN](https://github.com/borjalofe/blog/blob/main/content/posts/en/social-agent-0-2-0.md) · [ES](https://github.com/borjalofe/blog/blob/main/content/posts/es/social-agent-0-2-0.md)
- Network drafts live as vault `Publication` notes (LinkedIn / X / Medium); public URLs land when those posts ship

### Audit

- Post-release audit 2026-10-28: SCA/SAST clean; no `[FIX]` / PATCH — [docs/audits/0.2.0.md](docs/audits/0.2.0.md)

[0.2.0]: https://github.com/borjalofe/social-agent/releases/tag/0.2.0

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
