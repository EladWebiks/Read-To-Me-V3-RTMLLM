"""add scraping tables

Revision ID: 28416f944a82
Revises: 62d0e9dab375
Create Date: 2026-07-23 17:45:20.849952
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "28416f944a82"
down_revision: str | None = "62d0e9dab375"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scraping_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("base_domains", postgresql.ARRAY(sa.String(length=256)), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("rate_limit_seconds", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("terms_note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "scraping_jobs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("book_id", sa.UUID(), nullable=True),
        sa.Column("start_url", sa.String(length=2048), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False, server_default="full"),
        sa.Column("chapter_from", sa.Integer(), nullable=True),
        sa.Column("chapter_to", sa.Integer(), nullable=True),
        sa.Column("max_chapters", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("chapters_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["book_id"], ["books.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["scraping_sources.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scraping_jobs_user_id", "scraping_jobs", ["user_id"])
    op.create_index("ix_scraping_jobs_status", "scraping_jobs", ["status"])

    op.create_table(
        "scraping_job_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["scraping_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scraping_job_items_job_id", "scraping_job_items", ["job_id"])

    _seed_sources()


def _seed_sources() -> None:
    """Insert the four default scraping sources."""
    import uuid

    table = sa.table(
        "scraping_sources",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String),
        sa.column("base_domains", postgresql.ARRAY(sa.String)),
        sa.column("enabled", sa.Boolean),
        sa.column("rate_limit_seconds", sa.Float),
        sa.column("terms_note", sa.Text),
    )
    op.bulk_insert(
        table,
        [
            {
                "id": str(uuid.uuid4()),
                "name": "novelbin",
                "base_domains": "{novelbin.com}",
                "enabled": True,
                "rate_limit_seconds": 1.5,
                "terms_note": "",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "novelfull",
                "base_domains": "{novelfull.net}",
                "enabled": True,
                "rate_limit_seconds": 1.5,
                "terms_note": "",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "freewebnovel",
                "base_domains": "{freewebnovel.com}",
                "enabled": True,
                "rate_limit_seconds": 1.5,
                "terms_note": "",
            },
            {
                "id": str(uuid.uuid4()),
                "name": "novellunar",
                "base_domains": "{novellunar.com}",
                "enabled": True,
                "rate_limit_seconds": 1.5,
                "terms_note": "",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("scraping_job_items")
    op.drop_table("scraping_jobs")
    op.drop_table("scraping_sources")
