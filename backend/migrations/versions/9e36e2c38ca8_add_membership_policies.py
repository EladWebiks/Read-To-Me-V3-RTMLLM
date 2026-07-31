"""add membership_policies

Revision ID: 9e36e2c38ca8
Revises: cc8afb8f06aa
Create Date: 2026-07-31 13:52:15.808994
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9e36e2c38ca8"
down_revision: str | None = "cc8afb8f06aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "membership_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership", sa.String(length=32), nullable=False),
        # Per-turn caps: NULL = inherit the effective runtime setting.
        sa.Column(
            "max_tool_iters",
            sa.Integer(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
        sa.Column(
            "max_external_calls",
            sa.Integer(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
        sa.Column(
            "max_turn_tokens_in",
            sa.Integer(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
        sa.Column(
            "max_turn_tokens_out",
            sa.Integer(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
        sa.Column(
            "max_turn_cost_usd",
            sa.Float(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
        sa.Column(
            "run_deadline_seconds",
            sa.Integer(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
        sa.Column(
            "max_hitl_rounds",
            sa.Integer(),
            nullable=True,
            comment="NULL = inherit effective runtime setting",
        ),
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
    op.create_index(
        op.f("ix_membership_policies_membership"),
        "membership_policies",
        ["membership"],
        unique=True,
    )
    # Seed the CURRENT enum values, hardcoded — migrations must not import
    # app enums (replay determinism). Future values are seeded at startup.
    table = sa.table(
        "membership_policies",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("membership", sa.String()),
    )
    op.bulk_insert(table, [{"id": uuid.uuid4(), "membership": m} for m in ("free",)])


def downgrade() -> None:
    op.drop_index(op.f("ix_membership_policies_membership"), table_name="membership_policies")
    op.drop_table("membership_policies")
