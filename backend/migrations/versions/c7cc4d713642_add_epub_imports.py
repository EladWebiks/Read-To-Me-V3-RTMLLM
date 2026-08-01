"""add epub_imports

Revision ID: c7cc4d713642
Revises: 858710c83c59
Create Date: 2026-07-31 15:49:05.962924
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7cc4d713642"
down_revision: str | None = "858710c83c59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "epub_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
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
    )
    op.create_index(op.f("ix_epub_imports_user_id"), "epub_imports", ["user_id"])
    op.create_index(op.f("ix_epub_imports_status"), "epub_imports", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_epub_imports_status"), table_name="epub_imports")
    op.drop_index(op.f("ix_epub_imports_user_id"), table_name="epub_imports")
    op.drop_table("epub_imports")
