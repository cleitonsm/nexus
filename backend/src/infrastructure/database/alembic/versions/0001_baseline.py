"""Esquema do MVP.

Equivale aos arquivos SQL 0001 a 0003 e a coluna ``assistants.initial_prompt``,
antes criados por ``create_all`` na subida da API. E idempotente: em um banco
que ja tem as tabelas do MVP nada e recriado, apenas se completam as colunas
que versoes antigas nao tinham.

Revision ID: 0001_baseline
Revises:
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "assistants" not in tables:
        op.create_table(
            "assistants",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(80), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("initial_prompt", sa.Text(), nullable=True),
            _timestamp("created_at"),
        )
    elif not _has_column(inspector, "assistants", "initial_prompt"):
        op.add_column(
            "assistants",
            sa.Column("initial_prompt", sa.Text(), nullable=True),
        )

    if "documents" not in tables:
        op.create_table(
            "documents",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "assistant_id",
                sa.String(64),
                sa.ForeignKey("assistants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("source_name", sa.String(255), nullable=False),
            sa.Column("content_hash", sa.String(128), nullable=False),
            sa.Column(
                "metadata_json",
                sa.Text(),
                server_default="{}",
                nullable=False,
            ),
            _timestamp("created_at"),
        )

    if "conversations" not in tables:
        op.create_table(
            "conversations",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "assistant_id",
                sa.String(64),
                sa.ForeignKey("assistants.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("name", sa.String(100), nullable=True),
            _timestamp("created_at"),
            _timestamp("updated_at"),
        )
        op.create_index(
            "ix_conversations_assistant_id",
            "conversations",
            ["assistant_id"],
        )
    elif not _has_column(inspector, "conversations", "name"):
        op.add_column(
            "conversations",
            sa.Column("name", sa.String(100), nullable=True),
        )

    if "messages" not in tables:
        op.create_table(
            "messages",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "conversation_id",
                sa.String(64),
                sa.ForeignKey("conversations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(32), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            _timestamp("created_at"),
        )
        op.create_index(
            "ix_messages_conversation_id",
            "messages",
            ["conversation_id"],
        )

    if "secret_settings" not in tables:
        op.create_table(
            "secret_settings",
            sa.Column("key_name", sa.String(128), primary_key=True),
            sa.Column("encrypted_value", sa.Text(), nullable=False),
            _timestamp("created_at"),
            _timestamp("updated_at"),
        )


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(item["name"] == column for item in inspector.get_columns(table))


def downgrade() -> None:
    op.drop_table("secret_settings")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("documents")
    op.drop_table("assistants")
