"""SPEC-006: consumo por pergunta, configuracoes da tela e avaliacoes.

``usage_records`` nao tem chave estrangeira obrigatoria para a conversa: o
registro sobrevive a exclusao da conversa, para que apagar conversas nao
zere o limite diario (RN-32) nem o consumo do periodo (RF-57).

``message_feedback`` guarda copia da pergunta e da resposta nas avaliacoes
negativas, para o curador (RN-33); por isso tambem nao depende da mensagem.

Revision ID: 0006_operations
Revises: 0005_document_lifecycle
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_operations"
down_revision = "0005_document_lifecycle"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("user_name", sa.String(255), nullable=True),
        sa.Column(
            "conversation_id",
            sa.String(64),
            sa.ForeignKey(
                "conversations.id",
                name="fk_usage_records_conversation_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column(
            "assistant_id",
            sa.String(64),
            sa.ForeignKey(
                "assistants.id",
                name="fk_usage_records_assistant_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost",
            sa.Numeric(14, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("failed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_usage_records_user_occurred",
        "usage_records",
        ["user_id", "occurred_at"],
    )
    op.create_index("ix_usage_records_occurred", "usage_records", ["occurred_at"])
    op.create_index(
        "ix_usage_records_conversation", "usage_records", ["conversation_id"]
    )

    op.create_table(
        "app_settings",
        sa.Column("key_name", sa.String(64), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "message_feedback",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("message_id", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.String(64), nullable=False),
        sa.Column(
            "assistant_id",
            sa.String(64),
            sa.ForeignKey(
                "assistants.id",
                name="fk_message_feedback_assistant_id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("rating", sa.String(16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("cited_documents", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("source_documents", sa.JSON(), nullable=True),
        sa.Column(
            "out_of_scope", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "message_id", "user_id", name="uq_message_feedback_message_user"
        ),
    )
    op.create_index(
        "ix_message_feedback_assistant_status",
        "message_feedback",
        ["assistant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_message_feedback_assistant_status", table_name="message_feedback"
    )
    op.drop_table("message_feedback")
    op.drop_table("app_settings")
    op.drop_index("ix_usage_records_conversation", table_name="usage_records")
    op.drop_index("ix_usage_records_occurred", table_name="usage_records")
    op.drop_index("ix_usage_records_user_occurred", table_name="usage_records")
    op.drop_table("usage_records")
