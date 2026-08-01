"""add model catalog pricing and updated_at

Revision ID: 482eec614d32
Revises: e5e557d7c458
Create Date: 2026-07-30 18:17:58.071884
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "482eec614d32"
down_revision: str | None = "e5e557d7c458"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "model_configurations",
        sa.Column("input_cost_per_1m", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "model_configurations",
        sa.Column("output_cost_per_1m", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "model_configurations",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "model_providers",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Concurrent workers could have double-seeded before the unique constraint
    # existed; keep one row per (provider_id, model_name) before adding it.
    op.execute(
        sa.text(
            "DELETE FROM model_configurations a USING model_configurations b "
            "WHERE a.provider_id = b.provider_id "
            "AND a.model_name = b.model_name AND a.id > b.id"
        )
    )
    op.create_unique_constraint(
        "uq_model_configurations_provider_model",
        "model_configurations",
        ["provider_id", "model_name"],
    )
    # Backfill prices for rows seeded before this migration. Values are
    # duplicated from the code catalog on purpose — migrations never import
    # app code.
    op.execute(
        sa.text(
            "UPDATE model_configurations "
            "SET input_cost_per_1m = 0.10, output_cost_per_1m = 0.40 "
            "WHERE model_name = 'gemini-3.5-flash-lite'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE model_configurations "
            "SET input_cost_per_1m = 0.30, output_cost_per_1m = 2.50 "
            "WHERE model_name = 'gemini-3.6-flash'"
        )
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_model_configurations_provider_model",
        "model_configurations",
        type_="unique",
    )
    op.drop_column("model_providers", "updated_at")
    op.drop_column("model_configurations", "updated_at")
    op.drop_column("model_configurations", "output_cost_per_1m")
    op.drop_column("model_configurations", "input_cost_per_1m")
