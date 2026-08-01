"""add download_jobs size_bytes

Revision ID: 858710c83c59
Revises: b33fbafb70c4
Create Date: 2026-07-31 15:42:28.956952
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "858710c83c59"
down_revision: str | None = "b33fbafb70c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "download_jobs",
        sa.Column(
            "size_bytes",
            sa.BigInteger(),
            nullable=True,
            comment="MinIO bytes for this job; NULL = pre-column job",
        ),
    )


def downgrade() -> None:
    op.drop_column("download_jobs", "size_bytes")
