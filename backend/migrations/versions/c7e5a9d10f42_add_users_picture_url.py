"""add users picture_url

Revision ID: c7e5a9d10f42
Revises: db448309b4a6
Create Date: 2026-07-30 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e5a9d10f42"
down_revision: str | None = "db448309b4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("picture_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "picture_url")
