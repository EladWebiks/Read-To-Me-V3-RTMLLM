"""add membership_quotas

Revision ID: 3da225cd571b
Revises: 9e36e2c38ca8
Create Date: 2026-07-31 15:06:53.124170
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3da225cd571b"
down_revision: str | None = "9e36e2c38ca8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "membership_quotas",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership", sa.String(length=32), nullable=False),
        sa.Column("quota_kind", sa.String(length=32), nullable=False),
        sa.Column(
            "limit_value",
            sa.Float(),
            nullable=False,
            comment="Row absent = unlimited; there are no NULL limits",
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
        sa.UniqueConstraint("membership", "quota_kind", name="uq_membership_quotas_pair"),
    )
    op.create_index(op.f("ix_membership_quotas_membership"), "membership_quotas", ["membership"])


def downgrade() -> None:
    op.drop_index(op.f("ix_membership_quotas_membership"), table_name="membership_quotas")
    op.drop_table("membership_quotas")
