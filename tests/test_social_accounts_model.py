"""social_accounts table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import SocialAccount


def test_social_account_tablename_and_columns() -> None:
    assert SocialAccount.__tablename__ == "social_accounts"
    cols = {c.key: c for c in inspect(SocialAccount).columns}
    assert set(cols) == {
        "id",
        "user_id",
        "channel",
        "handle",
        "credentials_encrypted",
        "created_at",
        "updated_at",
    }
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["channel"].nullable is False
    assert cols["handle"].nullable is False
    assert cols["credentials_encrypted"].nullable is False


def test_social_account_unique_user_channel() -> None:
    names = {c.name for c in SocialAccount.__table__.constraints if c.name}
    assert "uq_social_accounts_user_id_channel" in names


def test_social_account_fk_to_users() -> None:
    fks = list(SocialAccount.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"
