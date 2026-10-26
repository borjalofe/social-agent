"""context_docs table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import ContextDoc


def test_context_doc_tablename_and_columns() -> None:
    assert ContextDoc.__tablename__ == "context_docs"
    cols = {c.key: c for c in inspect(ContextDoc).columns}
    assert set(cols) == {"id", "user_id", "title", "body", "created_at", "updated_at"}
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["title"].nullable is False
    assert cols["body"].nullable is False


def test_context_doc_user_id_not_unique() -> None:
    # Many context docs per user (unlike voice_docs).
    assert ContextDoc.__table__.c.user_id.unique is not True


def test_context_doc_fk_to_users() -> None:
    fks = list(ContextDoc.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"
