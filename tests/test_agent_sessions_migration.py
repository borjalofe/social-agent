"""Alembic migration for agent_sessions against Postgres."""

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


def test_upgrade_creates_agent_sessions_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "agent_sessions" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("agent_sessions")}
    assert set(cols) >= {
        "id",
        "user_id",
        "agent_name",
        "channel",
        "status",
        "created_at",
        "updated_at",
    }
    assert "payload" not in cols
    assert "body" not in cols
    pk = insp.get_pk_constraint("agent_sessions")
    assert pk["constrained_columns"] == ["id"]
    fks = insp.get_foreign_keys("agent_sessions")
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in fks
    )


def test_agent_sessions_meta_defaults_and_many_per_user(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "session-owner@example.com")
        for agent_name, channel in (
            ("copy_linkedin", "linkedin"),
            ("root_agent", None),
        ):
            conn.execute(
                text(
                    "INSERT INTO agent_sessions (id, user_id, agent_name, channel) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), "
                    ":agent_name, :channel)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "agent_name": agent_name,
                    "channel": channel,
                },
            )
        rows = conn.execute(
            text(
                "SELECT agent_name, channel, status FROM agent_sessions "
                "WHERE user_id = CAST(:user_id AS uuid) ORDER BY agent_name"
            ),
            {"user_id": user_id},
        ).all()
        assert len(rows) == 2
        assert {r.status for r in rows} == {"open"}
        assert {r.agent_name for r in rows} == {"copy_linkedin", "root_agent"}


def test_agent_sessions_fk_and_cascade(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO agent_sessions (id, user_id, agent_name) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :agent_name)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "agent_name": "orphan",
                },
            )

    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "session-cascade@example.com")
        conn.execute(
            text(
                "INSERT INTO agent_sessions (id, user_id, agent_name, status) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), "
                ":agent_name, :status)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "agent_name": "copy_x",
                "status": "waiting_approval",
            },
        )
        conn.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM agent_sessions")).scalar_one()
        assert count == 0


def test_downgrade_removes_agent_sessions_keeps_publications(database_url: str) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "agent_sessions" in inspect(engine).get_table_names()
    command.downgrade(cfg, "20261026_0007")
    names = inspect(engine).get_table_names()
    assert "agent_sessions" not in names
    assert "publications" in names
    assert "users" in names
    command.downgrade(cfg, "base")
    engine.dispose()
