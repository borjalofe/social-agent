"""users table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import User


def test_user_tablename_and_columns() -> None:
    assert User.__tablename__ == "users"
    cols = {c.key: c for c in inspect(User).columns}
    assert set(cols) == {"id", "email", "password_hash", "created_at", "updated_at"}
    assert cols["id"].primary_key
    assert cols["email"].nullable is False
    assert cols["password_hash"].nullable is False
    assert cols["email"].unique is True


def test_user_email_is_unique() -> None:
    assert User.__table__.c.email.unique is True
