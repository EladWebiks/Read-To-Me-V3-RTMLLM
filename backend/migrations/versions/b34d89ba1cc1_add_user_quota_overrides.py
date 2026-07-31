"""add user_quota_overrides

Revision ID: b34d89ba1cc1
Revises: e1e423eb1a7b
Create Date: 2026-07-31 20:33:28.464839
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b34d89ba1cc1"
down_revision: str | None = "e1e423eb1a7b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_quota_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "limit_value",
            sa.Float(),
            nullable=False,
            comment="Row absent = tier limit applies",
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id", "quota_kind", name="uq_user_quota_overrides_pair"),
    )
    op.create_index(op.f("ix_user_quota_overrides_user_id"), "user_quota_overrides", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_user_quota_overrides_user_id"), table_name="user_quota_overrides")
    op.drop_table("user_quota_overrides")
