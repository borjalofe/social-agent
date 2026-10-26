"""publications table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import Publication


def test_publication_tablename_and_columns() -> None:
    assert Publication.__tablename__ == "publications"
    cols = {c.key: c for c in inspect(Publication).columns}
    assert set(cols) == {
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
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["channel"].nullable is False
    assert cols["body"].nullable is False
    assert cols["status"].nullable is False
    assert cols["title"].nullable is True
    assert cols["scheduled_at"].nullable is True
    assert cols["published_at"].nullable is True


def test_publication_default_status_is_approved() -> None:
    assert Publication.__table__.c.status.default.arg == "approved"


def test_publication_fk_to_users() -> None:
    fks = list(Publication.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"


def test_publication_allows_many_per_user_channel() -> None:
    # Unlike canal_rules / social_accounts — many approved finals per channel.
    uniques = {
        tuple(col.name for col in c.columns)
        for c in Publication.__table__.constraints
        if c.__class__.__name__ == "UniqueConstraint"
    }
    assert ("user_id", "channel") not in uniques
