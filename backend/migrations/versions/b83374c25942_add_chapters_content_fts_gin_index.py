"""add chapters content fts gin index

Revision ID: b83374c25942
Revises: 6ff001d7073d
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b83374c25942"
down_revision: str | Sequence[str] | None = "6ff001d7073d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chapters_content_fts
        ON chapters
        USING GIN (
            to_tsvector(
                'english',
                coalesce(title, '') || ' ' || coalesce(content, '')
            )
        )
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chapters_content_fts")
