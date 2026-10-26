"""llm_connections table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import LlmConnection


def test_llm_connection_tablename_and_columns() -> None:
    assert LlmConnection.__tablename__ == "llm_connections"
    cols = {c.key: c for c in inspect(LlmConnection).columns}
    assert set(cols) == {
        "id",
        "user_id",
        "provider",
        "label",
        "credentials_encrypted",
        "created_at",
        "updated_at",
    }
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["provider"].nullable is False
    assert cols["label"].nullable is False
    assert cols["credentials_encrypted"].nullable is False


def test_llm_connection_unique_user_provider() -> None:
    names = {c.name for c in LlmConnection.__table__.constraints if c.name}
    assert "uq_llm_connections_user_id_provider" in names


def test_llm_connection_fk_to_users() -> None:
    fks = list(LlmConnection.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"
