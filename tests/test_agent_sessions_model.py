"""agent_sessions table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import AgentSession


def test_agent_session_tablename_and_columns() -> None:
    assert AgentSession.__tablename__ == "agent_sessions"
    cols = {c.key: c for c in inspect(AgentSession).columns}
    assert set(cols) == {
        "id",
        "user_id",
        "agent_name",
        "channel",
        "status",
        "created_at",
        "updated_at",
    }
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["agent_name"].nullable is False
    assert cols["status"].nullable is False
    assert cols["channel"].nullable is True


def test_agent_session_has_no_payload_column() -> None:
    # Payload belongs in Redis (#14), not Postgres.
    cols = {c.key for c in inspect(AgentSession).columns}
    assert "payload" not in cols
    assert "body" not in cols
    assert "data" not in cols


def test_agent_session_default_status_is_open() -> None:
    assert AgentSession.__table__.c.status.default.arg == "open"


def test_agent_session_fk_to_users() -> None:
    fks = list(AgentSession.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"
