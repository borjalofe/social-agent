"""ASGI entry: wire `create_app` from process environment (compose / local)."""

from __future__ import annotations

import os

from fastapi import FastAPI

from social_agent.api.app import create_app
from social_agent.auth.jwt_authn import JwtAuthn
from social_agent.auth.refresh_store import RedisRefreshTokenStore
from social_agent.sessions.redis_store import AgentSessionPayloadStore, redis_from_url


def create_app_from_env() -> FastAPI:
    """Build the API using JWT + Redis refresh/session stores from env.

    Siren resource stores stay in-memory until SQL adapters land; Postgres is for
    Alembic migrations (`alembic upgrade head`) against `DATABASE_URL`.
    """
    redis_client = redis_from_url()
    authn = JwtAuthn(refresh_store=RedisRefreshTokenStore(redis_client))
    fernet_key = os.environ.get("FERNET_KEY")
    return create_app(
        authn=authn,
        fernet_key=fernet_key if fernet_key else None,
        agent_run_payload_store=AgentSessionPayloadStore(redis_client),
    )
