"""add download_jobs deleted_at

Revision ID: b33fbafb70c4
Revises: 3da225cd571b
Create Date: 2026-07-31 15:35:22.194725
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b33fbafb70c4"
down_revision: str | None = "3da225cd571b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "download_jobs",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Soft delete: assets purged, row kept for quota metering",
        ),
    )
    op.create_index(op.f("ix_download_jobs_deleted_at"), "download_jobs", ["deleted_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_download_jobs_deleted_at"), table_name="download_jobs")
    op.drop_column("download_jobs", "deleted_at")
