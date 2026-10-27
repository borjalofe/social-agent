"""Contract: local compose + .env.example for runtime (issue #34)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"
COMPOSE = ROOT / "compose.yaml"
DOCKERFILE = ROOT / "Dockerfile"

REQUIRED_ENV_KEYS = (
    "JWT_SECRET",
    "FERNET_KEY",
    "DATABASE_URL",
    "REDIS_URL",
    "ANTHROPIC_API_KEY",
)


def test_env_example_lists_runtime_secrets() -> None:
    assert ENV_EXAMPLE.is_file()
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key in REQUIRED_ENV_KEYS:
        assert f"{key}=" in text, f"missing {key} in .env.example"
    assert "SOCIAL_AGENT_ROOT_MODEL=" in text


def test_compose_defines_db_redis_and_api() -> None:
    assert COMPOSE.is_file()
    cfg = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    services = cfg["services"]
    assert set(services) >= {"db", "redis", "api"}
    assert "postgres" in services["db"]["image"]
    assert "redis" in services["redis"]["image"]
    assert services["api"]["build"]["dockerfile"] == "Dockerfile"
    assert services["api"]["env_file"] == [".env"]
    env = services["api"]["environment"]
    assert "DATABASE_URL" in env
    assert "REDIS_URL" in env
    assert env["DATABASE_URL"].startswith("postgresql")
    assert "redis://" in env["REDIS_URL"]


def test_dockerfile_serves_uvicorn_factory() -> None:
    assert DOCKERFILE.is_file()
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "social_agent.api.main:create_app_from_env" in text
    assert "--factory" in text


def test_create_app_from_env_is_importable() -> None:
    from social_agent.api.main import create_app_from_env

    assert callable(create_app_from_env)
