"""voice_docs table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import VoiceDoc


def test_voice_doc_tablename_and_columns() -> None:
    assert VoiceDoc.__tablename__ == "voice_docs"
    cols = {c.key: c for c in inspect(VoiceDoc).columns}
    assert set(cols) == {"id", "user_id", "body", "created_at", "updated_at"}
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["body"].nullable is False


def test_voice_doc_user_id_unique() -> None:
    assert VoiceDoc.__table__.c.user_id.unique is True


def test_voice_doc_fk_to_users() -> None:
    fks = list(VoiceDoc.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"
