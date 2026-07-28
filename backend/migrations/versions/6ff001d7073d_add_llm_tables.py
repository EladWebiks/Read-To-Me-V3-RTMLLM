"""add_llm_tables

Revision ID: 6ff001d7073d
Revises: 28416f944a82
Create Date: 2026-07-28 12:29:26.767729
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6ff001d7073d"
down_revision: str | None = "28416f944a82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_providers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_providers_name"), "model_providers", ["name"], unique=True)
    op.create_table(
        "conversations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_conversations_user_id"), "conversations", ["user_id"], unique=False)
    op.create_table(
        "model_configurations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=False),
        sa.Column("supports_tools", sa.Boolean(), nullable=False),
        sa.Column("supports_structured", sa.Boolean(), nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["provider_id"], ["model_providers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_model_configurations_model_name"),
        "model_configurations",
        ["model_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_model_configurations_provider_id"),
        "model_configurations",
        ["provider_id"],
        unique=False,
    )
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_conversation_messages_conversation_id"),
        "conversation_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_table(
        "llm_executions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=True),
        sa.Column("task", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_llm_executions_conversation_id"),
        "llm_executions",
        ["conversation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_executions_provider"), "llm_executions", ["provider"], unique=False
    )
    op.create_index(op.f("ix_llm_executions_status"), "llm_executions", ["status"], unique=False)
    op.create_index(op.f("ix_llm_executions_task"), "llm_executions", ["task"], unique=False)
    op.create_index(
        op.f("ix_llm_executions_trace_id"), "llm_executions", ["trace_id"], unique=False
    )
    op.create_table(
        "cost_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("llm_execution_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("unit_cost_in", sa.Float(), nullable=False),
        sa.Column("unit_cost_out", sa.Float(), nullable=False),
        sa.Column("total_cost", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["llm_execution_id"], ["llm_executions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cost_records_llm_execution_id"),
        "cost_records",
        ["llm_execution_id"],
        unique=False,
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("confirmed_by_user", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["message_id"], ["conversation_messages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_calls_message_id"), "tool_calls", ["message_id"], unique=False)
    op.create_index(op.f("ix_tool_calls_status"), "tool_calls", ["status"], unique=False)
    op.create_index(op.f("ix_tool_calls_tool_name"), "tool_calls", ["tool_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_calls_tool_name"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_status"), table_name="tool_calls")
    op.drop_index(op.f("ix_tool_calls_message_id"), table_name="tool_calls")
    op.drop_table("tool_calls")
    op.drop_index(op.f("ix_cost_records_llm_execution_id"), table_name="cost_records")
    op.drop_table("cost_records")
    op.drop_index(op.f("ix_llm_executions_trace_id"), table_name="llm_executions")
    op.drop_index(op.f("ix_llm_executions_task"), table_name="llm_executions")
    op.drop_index(op.f("ix_llm_executions_status"), table_name="llm_executions")
    op.drop_index(op.f("ix_llm_executions_provider"), table_name="llm_executions")
    op.drop_index(op.f("ix_llm_executions_conversation_id"), table_name="llm_executions")
    op.drop_table("llm_executions")
    op.drop_index(
        op.f("ix_conversation_messages_conversation_id"),
        table_name="conversation_messages",
    )
    op.drop_table("conversation_messages")
    op.drop_index(op.f("ix_model_configurations_provider_id"), table_name="model_configurations")
    op.drop_index(op.f("ix_model_configurations_model_name"), table_name="model_configurations")
    op.drop_table("model_configurations")
    op.drop_index(op.f("ix_conversations_user_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_model_providers_name"), table_name="model_providers")
    op.drop_table("model_providers")
