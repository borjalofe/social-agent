# social-agent

Multi-user editorial agents behind Siren. Host: [github.com/borjalofe/social-agent](https://github.com/borjalofe/social-agent).

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16+ (for migrations / schema tests)

## Local quality gates (same as PR CI)

```bash
export DATABASE_URL=postgresql+psycopg://social:social@127.0.0.1:5432/social_agent_test
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run pip-audit
```

PR / `main` CI: `.github/workflows/ci.yml` (includes a Postgres service for migration tests).

Migration tests skip when `DATABASE_URL` is unset.

## Database migrations

Alembic manages schema:

- `users` — `id`, unique `email`, `password_hash`, timestamps
- `voice_docs` — one row per user (`user_id` FK → `users`, unique), `body` text, timestamps
- `context_docs` — many rows per user (`user_id` FK → `users`, indexed), `title`, `body`, timestamps
- `canal_rules` — one row per user+channel (`user_id` FK → `users`, unique `(user_id, channel)`), `body`, timestamps

```bash
export DATABASE_URL=postgresql+psycopg://social:social@127.0.0.1:5432/social_agent_test
uv run alembic upgrade head
uv run alembic downgrade base   # optional
```

## Daily audit

Scheduled workflow (`.github/workflows/audit.yml`, 06:00 UTC + `workflow_dispatch`) runs SCA (`pip-audit`) and SAST (`ruff` rule set `S`), then opens **one GitHub issue per new finding**. Dedupe uses a fingerprint of rule/id + path + normalized message embedded in the issue body (`audit-finding` label).

Dry-run locally (no GitHub calls):

```bash
uv run python -m social_agent.audit --dry-run
```
