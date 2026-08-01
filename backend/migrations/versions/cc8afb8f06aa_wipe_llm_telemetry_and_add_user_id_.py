"""wipe llm telemetry and add user_id attribution

DATA LOSS: intentionally deletes ALL rows from cost_records and
llm_executions (dev-only telemetry; approved fresh start so user_id can be
NOT NULL with no backfill). Downgrade removes the column/index/FK but the
wiped rows are unrecoverable in both directions.

Revision ID: cc8afb8f06aa
Revises: 482eec614d32
Create Date: 2026-07-30 19:14:16.273565
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cc8afb8f06aa"
down_revision: str | None = "482eec614d32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # FK order: cost_records.llm_execution_id references llm_executions.id,
    # so the child table is wiped first. cost_records is the only table
    # referencing llm_executions.
    op.execute(sa.text("DELETE FROM cost_records"))
    op.execute(sa.text("DELETE FROM llm_executions"))
    # Table is empty here, so NOT NULL needs no server_default.
    op.add_column(
        "llm_executions",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_llm_executions_user_id_users",
        "llm_executions",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index(
        "ix_llm_executions_user_id_created_at",
        "llm_executions",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_llm_executions_user_id_created_at", table_name="llm_executions")
    op.drop_constraint(
        "fk_llm_executions_user_id_users",
        "llm_executions",
        type_="foreignkey",
    )
    op.drop_column("llm_executions", "user_id")
