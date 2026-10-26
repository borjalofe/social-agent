"""Alembic migration for llm_connections against Postgres."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from social_agent.crypto.fernet_box import generate_key, seal, unseal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(scope="module")
def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set (Postgres required for migration tests)")
    return url


@pytest.fixture()
def migrated_engine(database_url: str) -> Iterator[object]:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    try:
        yield engine
    finally:
        command.downgrade(cfg, "base")
        engine.dispose()


def _insert_user(conn: object, user_id: str, email: str) -> None:
    conn.execute(
        text(
            "INSERT INTO users (id, email, password_hash) "
            "VALUES (CAST(:id AS uuid), :email, :password_hash)"
        ),
        {"id": user_id, "email": email, "password_hash": "hash-not-a-secret"},
    )


def test_upgrade_creates_llm_connections_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "llm_connections" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("llm_connections")}
    assert set(cols) >= {
        "id",
        "user_id",
        "provider",
        "label",
        "credentials_encrypted",
        "created_at",
        "updated_at",
    }
    pk = insp.get_pk_constraint("llm_connections")
    assert pk["constrained_columns"] == ["id"]
    fks = insp.get_foreign_keys("llm_connections")
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in fks
    )
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("llm_connections")}
    assert ("user_id", "provider") in uniques


def test_llm_connections_stores_fernet_ciphertext_not_plaintext(
    migrated_engine: object,
) -> None:
    user_id = str(uuid.uuid4())
    key = generate_key()
    plaintext = "sk-ant-api-test-secret"
    sealed = seal(plaintext, key=key)
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "llm-owner@example.com")
        conn.execute(
            text(
                "INSERT INTO llm_connections "
                "(id, user_id, provider, label, credentials_encrypted) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), "
                ":provider, :label, :credentials_encrypted)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "provider": "anthropic",
                "label": "Claude",
                "credentials_encrypted": sealed,
            },
        )
        row = conn.execute(
            text(
                "SELECT credentials_encrypted FROM llm_connections "
                "WHERE user_id = CAST(:user_id AS uuid)"
            ),
            {"user_id": user_id},
        ).one()
        assert row.credentials_encrypted == sealed
        assert plaintext not in row.credentials_encrypted
        assert unseal(row.credentials_encrypted, key=key) == plaintext


def test_llm_connections_unique_provider_and_cascade(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    key = generate_key()
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "llm-cascade@example.com")
        conn.execute(
            text(
                "INSERT INTO llm_connections "
                "(id, user_id, provider, label, credentials_encrypted) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), "
                ":provider, :label, :credentials_encrypted)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "provider": "openai",
                "label": "GPT",
                "credentials_encrypted": seal("sk-openai", key=key),
            },
        )

    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO llm_connections "
                    "(id, user_id, provider, label, credentials_encrypted) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), "
                    ":provider, :label, :credentials_encrypted)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "provider": "openai",
                    "label": "Other",
                    "credentials_encrypted": seal("other", key=key),
                },
            )

    with migrated_engine.begin() as conn:
        conn.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM llm_connections")).scalar_one()
        assert count == 0


def test_downgrade_removes_llm_connections_keeps_social_accounts(
    database_url: str,
) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "llm_connections" in inspect(engine).get_table_names()
    command.downgrade(cfg, "20261026_0005")
    names = inspect(engine).get_table_names()
    assert "llm_connections" not in names
    assert "social_accounts" in names
    assert "users" in names
    command.downgrade(cfg, "base")
    engine.dispose()
