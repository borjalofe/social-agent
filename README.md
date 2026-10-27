# social-agent

Multi-user editorial agents behind Siren. Host: [github.com/borjalofe/social-agent](https://github.com/borjalofe/social-agent).

**Version:** [0.1.0](CHANGELOG.md) (first M2 slice after ADK `copy_linkedin`).

**Announcement:** [EN](https://github.com/borjalofe/blog/blob/main/content/posts/en/social-agent-0-1-0.md) · [ES](https://github.com/borjalofe/blog/blob/main/content/posts/es/social-agent-0-1-0.md) (network drafts: vault Publications, linked from the post).

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

## Siren action authz (owner-only + 403)

Before offering Siren `actions`, filter them for the authenticated subject. Before executing a mutation, call `enforce` — unauthorized subjects raise `ForbiddenError` with `status_code == 403`.

M2 policy is owner-only (`OwnerOnlyPolicy`): a user may act only on resources they own. Admin / cross-user actions stay out of scope until later milestones.

```python
from uuid import uuid4
from social_agent.auth import ForbiddenError, SirenAction, SirenActionAuthz

authz = SirenActionAuthz()
owner, stranger = uuid4(), uuid4()
candidates = [
    SirenAction(name="update-voice", method="PUT", href="/voice"),
]
assert authz.filter_actions(owner, resource_owner_id=owner, candidates=candidates)
assert authz.filter_actions(stranger, resource_owner_id=owner, candidates=candidates) == []

authz.enforce(owner, resource_owner_id=owner, action="update-voice")
try:
    authz.enforce(stranger, resource_owner_id=owner, action="update-voice")
except ForbiddenError as exc:
    assert exc.status_code == 403

# Or strip actions from a Siren entity dict:
entity = authz.authorize_entity(
    {"class": ["voice"], "actions": [{"name": "update-voice", "method": "PUT", "href": "/voice"}]},
    stranger,
    resource_owner_id=owner,
)
assert entity["actions"] == []
```

## Siren home (entry + links)

Authenticated `GET /` returns a Siren home entity (`application/vnd.siren+json`) with catalog `links` to M2 resources (`user`, `voice`, `context`, …). Handlers for those paths land in later issues; home only publishes the entry map.

```bash
export JWT_SECRET='at-least-32-characters-of-secret!!'
export REDIS_URL=redis://127.0.0.1:6379/0
```

```python
from social_agent.api import create_app
from social_agent.auth import JwtAuthn
from social_agent.auth.refresh_store import RedisRefreshTokenStore
from social_agent.sessions.redis_store import redis_from_url

authn = JwtAuthn(refresh_store=RedisRefreshTokenStore(redis_from_url()))
app = create_app(authn=authn)
# uvicorn social_agent.api.app:…  — or pass `app` to your ASGI server.
# GET /  Authorization: Bearer <access_token>
```

Missing or invalid Bearer → `401`. The body is built by `build_home` and passed through `SirenActionAuthz.authorize_entity`.

## Siren user (profile)

Authenticated `GET /user` returns the caller's Siren profile (`class: ["user"]`) from access-token claims (`user_id`, `email`). No `password_hash` or other secrets. Links: `self` → `/user`, `home` → `/`.

```bash
# same JWT_SECRET / REDIS_URL as above
# GET /user  Authorization: Bearer <access_token>
```

```python
from social_agent.siren import build_user

entity = build_user(claims.user_id, email=claims.email)
```

## Siren voice

Authenticated `GET /voice` returns the caller's editorial voice (`class: ["voice"]`) with `body` and an `update-voice` action (`PUT /voice`). `PUT /voice` with JSON `{"body": "…"}` persists via the injected `VoiceStore` (default: in-memory; swap for Postgres-backed store at runtime).

```python
from social_agent.api import create_app
from social_agent.siren import InMemoryVoiceStore, build_voice

app = create_app(authn=authn, voice_store=InMemoryVoiceStore())
# GET|PUT /voice  Authorization: Bearer <access_token>
entity = build_voice(user_id, body="tono directo")
```

Missing or invalid Bearer → `401`. Unauthorized `update-voice` → `403`.

## Siren context

Authenticated context docs are a **collection** (many per user):

- `GET /context` — Siren collection + `add-context` (`POST /context`)
- `POST /context` — JSON `{"title": "…", "body": "…"}` → item entity
- `GET /context/{id}` — item with `update-context`
- `PUT /context/{id}` — update title/body

Default store is in-memory (`InMemoryContextStore`); inject a durable adapter for production. Cross-user ids return `404`.

```python
from social_agent.siren import InMemoryContextStore, build_context_collection

app = create_app(authn=authn, context_store=InMemoryContextStore())
```

## Siren canal-rules

One rules document per user+channel (matches `canal_rules` uniqueness):

- `GET /canal-rules` — collection + `add-canal-rule` (`POST`)
- `POST /canal-rules` — JSON `{"channel": "linkedin", "body": "…"}` (duplicate channel → `409`)
- `GET /canal-rules/{channel}` — item with `update-canal-rule`
- `PUT /canal-rules/{channel}` — JSON `{"body": "…"}`

Default store: `InMemoryCanalRuleStore`. Cross-user channels → `404`.

```python
from social_agent.siren import InMemoryCanalRuleStore

app = create_app(authn=authn, canal_rule_store=InMemoryCanalRuleStore())
```

## Siren social-accounts

One network binding per user+channel. Requests accept plaintext `credentials`; the API Fernet-seals them before storage. Siren responses expose only `handle` + `credentials_set` — never plaintext or ciphertext.

- `GET /social-accounts` — collection + `add-social-account`
- `POST /social-accounts` — `{"channel", "handle", "credentials"}` (duplicate → `409`)
- `GET /social-accounts/{channel}` — item with `update-social-account`
- `PUT /social-accounts/{channel}` — rotate `handle` + `credentials`

Requires `FERNET_KEY` (or `create_app(..., fernet_key=…)`).

```python
from social_agent.siren import InMemorySocialAccountStore

app = create_app(
    authn=authn,
    social_account_store=InMemorySocialAccountStore(),
    fernet_key=None,  # uses FERNET_KEY from the environment
)
```

## Siren llm-connections

One sealed LLM credential set per user+provider. Same confidentiality rules as social-accounts: Fernet at the API boundary; Siren exposes `provider`, `label`, `credentials_set` only.

- `GET /llm-connections` — collection + `add-llm-connection`
- `POST /llm-connections` — `{"provider", "label", "credentials"}` (duplicate → `409`)
- `GET /llm-connections/{provider}` — item with `update-llm-connection`
- `PUT /llm-connections/{provider}` — rotate `label` + `credentials`

```python
from social_agent.siren import InMemoryLlmConnectionStore

app = create_app(
    authn=authn,
    llm_connection_store=InMemoryLlmConnectionStore(),
)
```

## Siren publications

Approved finals only (`status`: `approved` | `scheduled` | `published`). Collection + entity for the calendar. Once `scheduled` or `published`, edits are locked (`update-publication` omitted; `PUT` → `409 publication_locked`).

- `GET /publications` — collection + `add-publication` (list entities omit `body`)
- `POST /publications` — `{"channel", "title?", "body", "status?", "scheduled_at?", "published_at?"}`
- `GET /publications/{id}` — item; `update-publication` only while `approved`
- `PUT /publications/{id}` — replace fields (blocked when locked)

```python
from social_agent.siren import InMemoryPublicationStore

app = create_app(authn=authn, publication_store=InMemoryPublicationStore())
```

## ADK root_agent (router)

Google ADK swarm entry: `root_agent` only routes to specialist sub-agents (it does not write channel copy). Default specialist: `copy_linkedin`. Override the model with `SOCIAL_AGENT_ROOT_MODEL` or `build_root_agent(model=…)`. Pass `sub_agents=[]` to clear defaults.

```python
from social_agent.agents import build_root_agent, root_agent

assert root_agent.name == "root_agent"
assert [a.name for a in root_agent.sub_agents] == ["copy_linkedin"]
router = build_root_agent(sub_agents=[])  # router only
```

## ADK InstructionProvider

Packs per-user editorial data from injectable stores into agent instructions: voice + context docs + canal rules. Never includes credentials (`social_accounts` / `llm_connections`). Use `pack(...)` for a static string or `for_agent(...)` as ADK `instruction=` (reads `ctx.user_id`; optional `channel` arg or `session.state["channel"]`).

```python
from social_agent.agents import InstructionProvider
from social_agent.siren import (
    InMemoryCanalRuleStore,
    InMemoryContextStore,
    InMemoryVoiceStore,
)

provider = InstructionProvider(
    voice_store=InMemoryVoiceStore(),
    context_store=InMemoryContextStore(),
    canal_rule_store=InMemoryCanalRuleStore(),
)
text = provider.pack(user_id, channel="linkedin", base_instruction="Write a post.")
# Agent(..., instruction=provider.for_agent("Write a post.", channel="linkedin"))
```

## ADK copy_linkedin

LinkedIn draft specialist: writes post copy only (no tools, no publish/approve). Wire `InstructionProvider` for per-user voice/context/`linkedin` canal rules. Model: `SOCIAL_AGENT_COPY_LINKEDIN_MODEL` or `SOCIAL_AGENT_ROOT_MODEL`.

```python
from social_agent.agents import InstructionProvider, build_copy_linkedin_agent, copy_linkedin_agent

assert copy_linkedin_agent.name == "copy_linkedin"
assert copy_linkedin_agent.tools == []

agent = build_copy_linkedin_agent(instruction_provider=provider)
# Agent instruction packs channel="linkedin" from the provider
```

## Siren agent-run

Starts an agent session (metadata + conversation payload). Invoking ADK `root_agent` from this resource lands later; for now it only creates/lists/gets sessions. Statuses: `open` | `waiting_approval` | `completed` | `failed` (start always `open`). Payload shape: `{agent_name, channel, input, turns, draft?}` — inject `AgentSessionPayloadStore` (Redis) in production.

- `GET /agent-run` — collection + `start-agent-run` (list entities omit `payload`)
- `POST /agent-run` — `{"agent_name", "channel?", "input?"}` → item with payload
- `GET /agent-run/{id}` — item with payload; `approve-draft` when status is `open`/`waiting_approval` and `payload.draft` is set
- `POST /agent-run/{id}/approve` — persist draft as an `approved` publication; mark run `completed` (body → calendar; `409` if no draft / already done)

```python
from social_agent.siren import InMemoryAgentRunPayloadStore, InMemoryAgentRunStore

app = create_app(
    authn=authn,
    agent_run_store=InMemoryAgentRunStore(),
    agent_run_payload_store=InMemoryAgentRunPayloadStore(),
)
# Or: agent_run_payload_store=AgentSessionPayloadStore(redis_from_url())
# Seed draft in payload, then POST /agent-run/{id}/approve
```

## Sealing LLM secrets (Fernet)

`llm_connections.credentials_encrypted` and social-account credentials must store Fernet ciphertext, never plaintext API keys.

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

Post-release manual audits (M2 after each `0.y.0`) live under `docs/audits/` — e.g. [0.1.0](docs/audits/0.1.0.md) (clean; no PATCH).
