"""add memberships registry

Revision ID: bfbd8f8ec4bb
Revises: b34d89ba1cc1
Create Date: 2026-08-01 00:03:15.442664
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "bfbd8f8ec4bb"
down_revision: str | None = "b34d89ba1cc1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price_label", sa.String(length=32), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
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
    op.create_index(op.f("ix_memberships_slug"), "memberships", ["slug"], unique=True)
    op.create_index(
        "uq_memberships_single_default",
        "memberships",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    # Backfill: 'free' first (hardcoded — migrations never import app code),
    # then any other slug already referenced anywhere, so the FKs are valid.
    op.execute(
        "INSERT INTO memberships (id, slug, label, rank, is_active, is_default) "
        f"VALUES ('{uuid.uuid4()}', 'free', 'Free', 0, true, true)"
    )
    op.execute(
        """
        INSERT INTO memberships (id, slug, label, rank, is_active, is_default)
        SELECT gen_random_uuid(), s.slug, s.slug, 0, true, false FROM (
            SELECT membership AS slug FROM users
            UNION SELECT membership FROM membership_policies
            UNION SELECT membership FROM membership_quotas
        ) s WHERE s.slug NOT IN (SELECT slug FROM memberships)
        """
    )
    op.create_foreign_key(
        "fk_users_membership_memberships", "users", "memberships", ["membership"], ["slug"]
    )
    op.create_foreign_key(
        "fk_membership_policies_membership_memberships",
        "membership_policies",
        "memberships",
        ["membership"],
        ["slug"],
    )
    op.create_foreign_key(
        "fk_membership_quotas_membership_memberships",
        "membership_quotas",
        "memberships",
        ["membership"],
        ["slug"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_membership_quotas_membership_memberships", "membership_quotas", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_membership_policies_membership_memberships", "membership_policies", type_="foreignkey"
    )
    op.drop_constraint("fk_users_membership_memberships", "users", type_="foreignkey")
    op.drop_index("uq_memberships_single_default", table_name="memberships")
    op.drop_index(op.f("ix_memberships_slug"), table_name="memberships")
    op.drop_table("memberships")
