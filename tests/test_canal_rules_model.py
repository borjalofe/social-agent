"""canal_rules table model contract (no live database)."""

from __future__ import annotations

from sqlalchemy import inspect

from social_agent.db.models import CanalRule


def test_canal_rule_tablename_and_columns() -> None:
    assert CanalRule.__tablename__ == "canal_rules"
    cols = {c.key: c for c in inspect(CanalRule).columns}
    assert set(cols) == {"id", "user_id", "channel", "body", "created_at", "updated_at"}
    assert cols["id"].primary_key
    assert cols["user_id"].nullable is False
    assert cols["channel"].nullable is False
    assert cols["body"].nullable is False


def test_canal_rule_unique_user_channel() -> None:
    names = {c.name for c in CanalRule.__table__.constraints if c.name}
    assert "uq_canal_rules_user_id_channel" in names


def test_canal_rule_fk_to_users() -> None:
    fks = list(CanalRule.__table__.foreign_keys)
    assert len(fks) == 1
    assert fks[0].column.table.name == "users"
    assert fks[0].column.name == "id"
