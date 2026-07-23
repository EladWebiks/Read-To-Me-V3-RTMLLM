"""add download_jobs expires_at

Revision ID: 62d0e9dab375
Revises: df070bcf074d
Create Date: 2026-07-23 17:12:07.895222
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "62d0e9dab375"
down_revision: str | None = "df070bcf074d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "download_jobs",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f("ix_download_jobs_expires_at"),
        "download_jobs",
        ["expires_at"],
        unique=False,
    )
    op.execute(
        sa.text(
            "UPDATE download_jobs "
            "SET expires_at = created_at + interval '72 hours' "
            "WHERE expires_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_download_jobs_expires_at"), table_name="download_jobs")
    op.drop_column("download_jobs", "expires_at")
