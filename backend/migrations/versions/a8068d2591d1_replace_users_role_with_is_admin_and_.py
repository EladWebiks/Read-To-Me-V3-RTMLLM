"""replace users role with is_admin and membership

Revision ID: a8068d2591d1
Revises: c7e5a9d10f42
Create Date: 2026-07-30 14:24:59.067782
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8068d2591d1"
down_revision: str | None = "c7e5a9d10f42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("membership", sa.String(length=32), nullable=False, server_default="free"),
    )
    op.execute(sa.text("UPDATE users SET is_admin = TRUE WHERE role = 'admin'"))
    op.drop_column("users", "role")


def downgrade() -> None:
    # Recreate role from is_admin; original column had NOT NULL and no
    # server default, so backfill through a temporary default then drop it.
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE is_admin"))
    op.alter_column("users", "role", server_default=None)
    op.drop_column("users", "membership")
    op.drop_column("users", "is_admin")
