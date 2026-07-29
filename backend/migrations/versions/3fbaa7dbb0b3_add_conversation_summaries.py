"""add conversation summaries

Revision ID: 3fbaa7dbb0b3
Revises: 2cc7917588f9
Create Date: 2026-07-29 15:47:09.357489
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3fbaa7dbb0b3"
down_revision: str | None = "2cc7917588f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("through_message_id", sa.UUID(), nullable=False),
        sa.Column("source_message_count", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["through_message_id"], ["conversation_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_summaries_conversation_id"),
        "conversation_summaries",
        ["conversation_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_conversation_summaries_through_message_id"),
        "conversation_summaries",
        ["through_message_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_summaries_user_id"),
        "conversation_summaries",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_summaries_user_id"), table_name="conversation_summaries")
    op.drop_index(
        op.f("ix_conversation_summaries_through_message_id"),
        table_name="conversation_summaries",
    )
    op.drop_index(
        op.f("ix_conversation_summaries_conversation_id"),
        table_name="conversation_summaries",
    )
    op.drop_table("conversation_summaries")
