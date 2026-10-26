"""Alembic migration for voice_docs against Postgres."""

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


def test_upgrade_creates_voice_docs_table(migrated_engine: object) -> None:
    insp = inspect(migrated_engine)
    assert "voice_docs" in insp.get_table_names()
    cols = {c["name"]: c for c in insp.get_columns("voice_docs")}
    assert set(cols) >= {"id", "user_id", "body", "created_at", "updated_at"}
    pk = insp.get_pk_constraint("voice_docs")
    assert pk["constrained_columns"] == ["id"]
    fks = insp.get_foreign_keys("voice_docs")
    assert any(
        fk["referred_table"] == "users" and fk["constrained_columns"] == ["user_id"] for fk in fks
    )
    uniques = {tuple(u["column_names"]) for u in insp.get_unique_constraints("voice_docs")}
    unique_idx = {
        tuple(i["column_names"]) for i in insp.get_indexes("voice_docs") if i.get("unique")
    }
    assert ("user_id",) in uniques or ("user_id",) in unique_idx


def test_voice_docs_fk_unique_and_roundtrip(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    doc_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "voice-owner@example.com")
        conn.execute(
            text(
                "INSERT INTO voice_docs (id, user_id, body) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :body)"
            ),
            {"id": doc_id, "user_id": user_id, "body": "# Voice\n\nBe concrete."},
        )
        row = conn.execute(
            text("SELECT body FROM voice_docs WHERE id = CAST(:id AS uuid)"),
            {"id": doc_id},
        ).one()
        assert row.body == "# Voice\n\nBe concrete."

    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO voice_docs (id, user_id, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "body": "second doc for same user",
                },
            )

    with migrated_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO voice_docs (id, user_id, body) "
                    "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :body)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": str(uuid.uuid4()),
                    "body": "orphan",
                },
            )


def test_voice_docs_cascade_on_user_delete(migrated_engine: object) -> None:
    user_id = str(uuid.uuid4())
    with migrated_engine.begin() as conn:
        _insert_user(conn, user_id, "cascade@example.com")
        conn.execute(
            text(
                "INSERT INTO voice_docs (id, user_id, body) "
                "VALUES (CAST(:id AS uuid), CAST(:user_id AS uuid), :body)"
            ),
            {"id": str(uuid.uuid4()), "user_id": user_id, "body": "temp"},
        )
        conn.execute(
            text("DELETE FROM users WHERE id = CAST(:id AS uuid)"),
            {"id": user_id},
        )
        count = conn.execute(text("SELECT COUNT(*) FROM voice_docs")).scalar_one()
        assert count == 0


def test_downgrade_removes_voice_docs_keeps_users(database_url: str) -> None:
    engine = create_engine(database_url)
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    assert "voice_docs" in inspect(engine).get_table_names()
    command.downgrade(cfg, "20261026_0001")
    names = inspect(engine).get_table_names()
    assert "voice_docs" not in names
    assert "users" in names
    command.downgrade(cfg, "base")
    engine.dispose()
