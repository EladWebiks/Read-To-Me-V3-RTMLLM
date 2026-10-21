"""add tool_calls user_id attribution

Revision ID: a1c2d3e4f5b6
Revises: bfbd8f8ec4bb
Create Date: 2026-08-03 22:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c2d3e4f5b6"
down_revision: str | None = "bfbd8f8ec4bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tool_calls",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tool_calls_user_id_users",
        "tool_calls",
        "users",
        ["user_id"],
        ["id"],
    )
    op.create_index(op.f("ix_tool_calls_user_id"), "tool_calls", ["user_id"])
    # Legacy attribution: message → conversation owner.
    op.execute(
        """
        UPDATE tool_calls AS tc
        SET user_id = c.user_id
        FROM conversation_messages AS cm
        JOIN conversations AS c ON c.id = cm.conversation_id
        WHERE tc.message_id = cm.id
          AND tc.user_id IS NULL
        """
    )
    # HITL freeze snapshots store conversation_id in output JSON.
    op.execute(
        """
        UPDATE tool_calls AS tc
        SET user_id = c.user_id
        FROM conversations AS c
        WHERE tc.user_id IS NULL
          AND tc.output ? 'conversation_id'
          AND (tc.output->>'conversation_id') ~*
              '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
          AND c.id = (tc.output->>'conversation_id')::uuid
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_calls_user_id"), table_name="tool_calls")
    op.drop_constraint("fk_tool_calls_user_id_users", "tool_calls", type_="foreignkey")
    op.drop_column("tool_calls", "user_id")
