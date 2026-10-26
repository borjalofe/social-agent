"""Alembic migration for canal_rules against Postgres."""

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


def test_upgrade_creates_canal_rules_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "canal_rules" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("canal_rules")}
    assert set(cols) >= {"id", "user_id", "channel", "body", "created_at", "updated_at"}
    pk = insp.get_pk_constraint("canal_rules")
    assert pk["constrained_columns"] == ["id"]
    fks = insp.get_foreign_keys("canal_rules")
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in fks
    )
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("canal_rules")}
    assert ("user_id", "channel") in uniques


def test_canal_rules_unique_per_user_channel(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "canal-owner@example.com")
        conn.execute(
            text(
                "INSERT INTO canal_rules (id, user_id, channel, body) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "channel": "linkedin",
                "body": "Keep posts concrete.",
            },
        )
        conn.execute(
            text(
                "INSERT INTO canal_rules (id, user_id, channel, body) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "channel": "x",
                "body": "Short punchy posts.",
            },
        )
        count = conn.execute(
            text("SELECT COUNT(*) FROM canal_rules WHERE user_id = CAST(:user_id AS uuid)"),
            {"user_id": user_id},
        ).scalar_one()
        assert count == 2

    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO canal_rules (id, user_id, channel, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "channel": "linkedin",
                    "body": "duplicate channel",
                },
            )


def test_canal_rules_fk_and_cascade(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO canal_rules (id, user_id, channel, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "channel": "blog",
                    "body": "orphan",
                },
            )

    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "cascade-canal@example.com")
        conn.execute(
            text(
                "INSERT INTO canal_rules (id, user_id, channel, body) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "channel": "medium",
                "body": "temp",
            },
        )
        conn.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM canal_rules")).scalar_one()
        assert count == 0


def test_downgrade_removes_canal_rules_keeps_context_docs(database_url: str) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "canal_rules" in inspect(engine).get_table_names()
    command.downgrade(cfg, "20261026_0003")
    names = inspect(engine).get_table_names()
    assert "canal_rules" not in names
    assert "context_docs" in names
    assert "users" in names
    command.downgrade(cfg, "base")
    engine.dispose()
