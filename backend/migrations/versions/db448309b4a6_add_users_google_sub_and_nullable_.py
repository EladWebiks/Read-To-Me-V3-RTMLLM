"""add users google_sub and nullable password_hash

Revision ID: db448309b4a6
Revises: 3fbaa7dbb0b3
Create Date: 2026-07-29 21:37:34.931682
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "db448309b4a6"
down_revision: str | None = "3fbaa7dbb0b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    # Google-provisioned users have no password; use an unusable sentinel so
    # the NOT NULL constraint can be restored.
    op.execute(sa.text("UPDATE users SET password_hash = '' WHERE password_hash IS NULL"))
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_column("users", "google_sub")
