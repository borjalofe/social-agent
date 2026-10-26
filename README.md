# social-agent

Multi-user editorial agents behind Siren. Host: [github.com/borjalofe/social-agent](https://github.com/borjalofe/social-agent).

## Requirements

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16+ (for migrations / schema tests)
- Redis 7+ (for agent session payload tests / runtime)

## Local quality gates (same as PR CI)

```bash
export DATABASE_URL=postgresql+psycopg://social:social@127.0.0.1:5432/social_agent_test
export REDIS_URL=redis://127.0.0.1:6379/0
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv run pip-audit
```

PR / `main` CI: `.github/workflows/ci.yml` (Postgres + Redis services).

Migration tests skip when `DATABASE_URL` is unset. Redis integration tests skip when `REDIS_URL` is unset.

## Database migrations

Alembic manages schema:

- `users` — `id`, unique `email`, `password_hash`, timestamps
- `voice_docs` — one row per user (`user_id` FK → `users`, unique), `body` text, timestamps
- `context_docs` — many rows per user (`user_id` FK → `users`, indexed), `title`, `body`, timestamps
- `canal_rules` — one row per user+channel (`user_id` FK → `users`, unique `(user_id, channel)`), `body`, timestamps
- `social_accounts` — one row per user+channel (`handle`, opaque `credentials_encrypted`), unique `(user_id, channel)`
- `llm_connections` — one row per user+provider (`label`, Fernet `credentials_encrypted`), unique `(user_id, provider)`
- `publications` — approved finals only (many per user+channel); `status` / `scheduled_at` / `published_at` for calendar
- `agent_sessions` — session metadata only (`agent_name`, optional `channel`, `status`); payload in Redis via `AgentSessionPayloadStore`

```bash
export DATABASE_URL=postgresql+psycopg://social:social@127.0.0.1:5432/social_agent_test
uv run alembic upgrade head
uv run alembic downgrade base   # optional
```

## Agent session payloads (Redis)

Postgres `agent_sessions` holds metadata. Conversation/draft JSON lives in Redis under `agent_session:{uuid}` with a default TTL of 7 days.

```python
from uuid import uuid4
from social_agent.sessions import AgentSessionPayloadStore
from social_agent.sessions.redis_store import redis_from_url

store = AgentSessionPayloadStore(redis_from_url())  # uses REDIS_URL
session_id = uuid4()
store.put(session_id, {"draft": "…", "turns": []})
payload = store.get(session_id)
store.delete(session_id)
```

## JWT authn (access + refresh)

Issue short-lived access JWTs and longer-lived refresh JWTs. Refresh tokens are rotated: each use consumes the `jti` stored in Redis (`refresh_jti:{jti}`). Reuse of an old refresh token raises `TokenReuseError`.

```bash
export JWT_SECRET='at-least-32-characters-of-secret!!'
export REDIS_URL=redis://127.0.0.1:6379/0
```

```python
from uuid import uuid4
from social_agent.auth import JwtAuthn
from social_agent.auth.refresh_store import RedisRefreshTokenStore
from social_agent.sessions.redis_store import redis_from_url

authn = JwtAuthn(refresh_store=RedisRefreshTokenStore(redis_from_url()))
pair = authn.issue_pair(uuid4(), email="user@example.com")
claims = authn.verify_access(pair.access_token)
rotated = authn.rotate(pair.refresh_token)
# TokenPair.__repr__ redacts secrets — never log access_token / refresh_token.
```

## Sealing LLM secrets (Fernet)

`llm_connections.credentials_encrypted` must store Fernet ciphertext, never plaintext API keys.

```bash
# Generate a key once; keep it only in the environment (compose lands in a later task).
uv run python -c "from social_agent.crypto import generate_key; print(generate_key().decode())"
export FERNET_KEY=...   # value from generate_key
```

```python
from social_agent.crypto import seal, unseal

token = seal("sk-ant-...")  # uses FERNET_KEY
secret = unseal(token)
```

## Daily audit

Scheduled workflow (`.github/workflows/audit.yml`, 06:00 UTC + `workflow_dispatch`) runs SCA (`pip-audit`) and SAST (`ruff` rule set `S`), then opens **one GitHub issue per new finding**. Dedupe uses a fingerprint of rule/id + path + normalized message embedded in the issue body (`audit-finding` label).

Dry-run locally (no GitHub calls):

```bash
uv run python -m social_agent.audit --dry-run
```
