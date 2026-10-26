"""Alembic migration for users against Postgres."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _database_url() -> str | None:
    return os.environ.get("DATABASE_URL")


@pytest.fixture(scope="module")
def database_url() -> str:
    url = _database_url()
    if not url:
        pytest.skip("DATABASE_URL not set (Postgres required for migration tests)")
    return url


@pytest.fixture()
def migrated_engine(database_url: str) -> Iterator[object]:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    # Isolate: drop public schema objects between tests via downgrade/upgrade
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    try:
        yield engine
    finally:
        command.downgrade(cfg, "base")
        engine.dispose()


def test_upgrade_creates_users_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "users" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert set(cols) >= {"id", "email", "password_hash", "created_at", "updated_at"}
    pk = insp.get_pk_constraint("users")
    assert pk["constrained_columns"] == ["id"]
    uniques = insp.get_unique_constraints("users")
    unique_cols = {tuple(u["column_names"]) for u in uniques}
    indexes = insp.get_indexes("users")
    unique_idx = {tuple(i["column_names"]) for i in indexes if i.get("unique")}
    assert ("email",) in unique_cols or ("email",) in unique_idx


def test_users_email_unique_and_roundtrip(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash) "
                "VALUES (CAST(:id AS uuid), :email, :password_hash)"
            ),
            {
                "id": user_id,
                "email": "alice@example.com",
                "password_hash": "hash-not-a-secret",
            },
        )
        row = conn.execute(
            text("SELECT email, password_hash FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        ).one()
        assert row.email == "alice@example.com"
        assert row.password_hash == "hash-not-a-secret"

    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash) "
                    "VALUES (CAST(:id AS uuid), :email, :password_hash)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "email": "alice@example.com",
                    "password_hash": "other",
                },
            )


def test_downgrade_removes_users_table(database_url: str) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "users" in inspect(engine).get_table_names()
    command.downgrade(cfg, "base")
    assert "users" not in inspect(engine).get_table_names()
    engine.dispose()
