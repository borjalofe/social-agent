"""Alembic migration for context_docs against Postgres."""

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


def test_upgrade_creates_context_docs_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "context_docs" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("context_docs")}
    assert set(cols) >= {"id", "user_id", "title", "body", "created_at", "updated_at"}
    pk = insp.get_pk_constraint("context_docs")
    assert pk["constrained_columns"] == ["id"]
    fks = insp.get_foreign_keys("context_docs")
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in fks
    )
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("context_docs")}
    unique_idx = {
        tuple(i["column_names"]) for i in insp.get_indexes("context_docs") if i.get("unique")
    }
    assert ("user_id",) not in uniques
    assert ("user_id",) not in unique_idx


def test_context_docs_allows_many_per_user(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "ctx-owner@example.com")
        for title, body in (
            ("Product", "Facts about the product."),
            ("Audience", "Who we write for."),
        ):
            conn.execute(
                text(
                    "INSERT INTO context_docs (id, user_id, title, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :title, :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "title": title,
                    "body": body,
                },
            )
        count = conn.execute(
            text("SELECT COUNT(*) FROM context_docs WHERE user_id = CAST(:user_id AS uuid)"),
            {"user_id": user_id},
        ).scalar_one()
        assert count == 2


def test_context_docs_fk_and_cascade(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO context_docs (id, user_id, title, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :title, :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "title": "Orphan",
                    "body": "no user",
                },
            )

    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "cascade-ctx@example.com")
        conn.execute(
            text(
                "INSERT INTO context_docs (id, user_id, title, body) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :title, :body)"
            ),
            {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": "Temp",
                "body": "gone soon",
            },
        )
        conn.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM context_docs")).scalar_one()
        assert count == 0


def test_downgrade_removes_context_docs_keeps_voice_docs(database_url: str) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "context_docs" in inspect(engine).get_table_names()
    command.downgrade(cfg, "20261026_0002")
    names = inspect(engine).get_table_names()
    assert "context_docs" not in names
    assert "voice_docs" in names
    assert "users" in names
    command.downgrade(cfg, "base")
    engine.dispose()
