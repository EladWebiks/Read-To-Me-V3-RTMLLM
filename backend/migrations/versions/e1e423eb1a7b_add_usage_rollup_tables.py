"""add usage rollup tables

Revision ID: e1e423eb1a7b
Revises: c7cc4d713642
Create Date: 2026-07-31 16:10:35.930955
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1e423eb1a7b"
down_revision: str | None = "c7cc4d713642"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("metric", sa.String(length=48), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
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
        sa.UniqueConstraint("user_id", "day", "metric", name="uq_usage_daily_key"),
    )
    op.create_index(op.f("ix_usage_daily_user_id"), "usage_daily", ["user_id"])
    op.create_index(op.f("ix_usage_daily_day"), "usage_daily", ["day"])
    op.create_table(
        "llm_model_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("tokens_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("executions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "provider", "model", name="uq_llm_model_daily_key"),
    )
    op.create_index(op.f("ix_llm_model_daily_day"), "llm_model_daily", ["day"])
    op.create_table(
        "llm_task_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("tokens_in", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("executions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("day", "task", name="uq_llm_task_daily_key"),
    )
    op.create_index(op.f("ix_llm_task_daily_day"), "llm_task_daily", ["day"])
    op.create_table(
        "quota_rejections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quota_rejections_user_id"), "quota_rejections", ["user_id"])
    op.create_index(op.f("ix_quota_rejections_created_at"), "quota_rejections", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_quota_rejections_created_at"), table_name="quota_rejections")
    op.drop_index(op.f("ix_quota_rejections_user_id"), table_name="quota_rejections")
    op.drop_table("quota_rejections")
    op.drop_index(op.f("ix_llm_task_daily_day"), table_name="llm_task_daily")
    op.drop_table("llm_task_daily")
    op.drop_index(op.f("ix_llm_model_daily_day"), table_name="llm_model_daily")
    op.drop_table("llm_model_daily")
    op.drop_index(op.f("ix_usage_daily_day"), table_name="usage_daily")
    op.drop_index(op.f("ix_usage_daily_user_id"), table_name="usage_daily")
    op.drop_table("usage_daily")
