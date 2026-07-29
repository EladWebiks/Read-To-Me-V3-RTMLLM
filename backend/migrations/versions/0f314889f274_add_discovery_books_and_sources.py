"""add discovery books and sources

Revision ID: 0f314889f274
Revises: b83374c25942
Create Date: 2026-07-28 20:45:29.299747
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0f314889f274"
down_revision: str | None = "b83374c25942"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovered_books",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("normalized_title", sa.String(length=512), nullable=False),
        sa.Column("author", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
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
    )
    op.create_index(
        op.f("ix_discovered_books_normalized_title"),
        "discovered_books",
        ["normalized_title"],
        unique=False,
    )
    op.create_table(
        "book_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("discovered_book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("book_url", sa.String(length=2048), nullable=False),
        sa.Column("first_chapter_url", sa.String(length=2048), nullable=False),
        sa.Column("chapter_count_estimate", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["discovered_book_id"],
            ["discovered_books.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("source", "book_url", name="uq_book_sources_source_url"),
    )
    op.create_index(
        op.f("ix_book_sources_discovered_book_id"),
        "book_sources",
        ["discovered_book_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_book_sources_source"),
        "book_sources",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_book_sources_source"), table_name="book_sources")
    op.drop_index(op.f("ix_book_sources_discovered_book_id"), table_name="book_sources")
    op.drop_table("book_sources")
    op.drop_index(
        op.f("ix_discovered_books_normalized_title"),
        table_name="discovered_books",
    )
    op.drop_table("discovered_books")
