"""create agent_sessions table

Revision ID: 20261026_0008
Revises: 20261026_0007
Create Date: 2026-10-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261026_0008"
down_revision: str | Sequence[str] | None = "20261026_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="open",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_sessions_user_id", "agent_sessions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_sessions_user_id", table_name="agent_sessions")
    op.drop_table("agent_sessions")
