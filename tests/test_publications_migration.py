"""Alembic migration for publications against Postgres."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

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


def test_upgrade_creates_publications_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "publications" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("publications")}
    assert set(cols) >= {
        "id",
        "user_id",
        "channel",
        "title",
        "body",
        "status",
        "scheduled_at",
        "published_at",
        "created_at",
        "updated_at",
    }
    pk = insp.get_pk_constraint("publications")
    assert pk["constrained_columns"] == ["id"]
    fks = insp.get_foreign_keys("publications")
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in fks
    )
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("publications")}
    assert ("user_id", "channel") not in uniques


def test_publications_many_per_channel_default_status(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "pub-owner@example.com")
        for body in ("First approved post", "Second approved post"):
            conn.execute(
                text(
                    "INSERT INTO publications (id, user_id, channel, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "channel": "linkedin",
                    "body": body,
                },
            )
        rows = conn.execute(
            text(
                "SELECT body, status FROM publications "
                "WHERE user_id = CAST(:user_id AS uuid) ORDER BY body"
            ),
            {"user_id": user_id},
        ).all()
        assert len(rows) == 2
        assert {r.status for r in rows} == {"approved"}


def test_publications_schedule_fields_and_fk(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    when = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO publications (id, user_id, channel, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :channel, :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "channel": "x",
                    "body": "orphan",
                },
            )

    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "pub-sched@example.com")
        conn.execute(
            text(
                "INSERT INTO publications "
                "(id, user_id, channel, title, body, status, scheduled_at) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), "
                ":channel, :title, :body, :status, :scheduled_at)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "channel": "blog",
                "title": "Ship log",
                "body": "Approved final",
                "status": "scheduled",
                "scheduled_at": when,
            },
        )
        row = conn.execute(
            text(
                "SELECT title, status, scheduled_at FROM publications "
                "WHERE user_id = CAST(:user_id AS uuid)"
            ),
            {"user_id": user_id},
        ).one()
        assert row.title == "Ship log"
        assert row.status == "scheduled"
        assert row.scheduled_at == when

        conn.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM publications")).scalar_one()
        assert count == 0


def test_downgrade_removes_publications_keeps_llm_connections(database_url: str) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "publications" in inspect(engine).get_table_names()
    command.downgrade(cfg, "20261026_0006")
    names = inspect(engine).get_table_names()
    assert "publications" not in names
    assert "llm_connections" in names
    assert "users" in names
    command.downgrade(cfg, "base")
    engine.dispose()
