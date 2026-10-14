"""fix-13: indices, CHECKs de status e ``details`` da auditoria em JSONB.

Revision ID: 0008_indexes_and_constraints
Revises: 0007_reindex_in_worker
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_indexes_and_constraints"
down_revision = "0007_reindex_in_worker"
branch_labels = None
depends_on = None

_CHECKS = (
    (
        "documents",
        "ck_documents_status",
        "status IN ('pendente', 'processando', 'indexado', 'falhou', 'substituido')",
    ),
    (
        "ingestion_jobs",
        "ck_ingestion_jobs_status",
        "status IN ('pendente', 'processando', 'concluido', 'falhou')",
    ),
    (
        "reindex_jobs",
        "ck_reindex_jobs_status",
        "status IN ('running', 'succeeded', 'failed')",
    ),
    (
        "message_feedback",
        "ck_message_feedback_status",
        "status IN ('nao_aplicavel', 'pendente', 'validado', 'descartado')",
    ),
)

_INDEXES = (
    (
        "ix_conversations_owner_assistant_updated",
        "conversations",
        ["owner_user_id", "assistant_id", "updated_at"],
    ),
    (
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    ),
    ("ix_usage_records_assistant", "usage_records", ["assistant_id"]),
    ("ix_documents_replaces_document_id", "documents", ["replaces_document_id"]),
)


def upgrade() -> None:
    for name, table, columns in _INDEXES:
        op.create_index(name, table, columns)
    # json -> jsonb permite o indice de expressao abaixo (sem varredura completa).
    op.alter_column(
        "audit_events",
        "details",
        type_=postgresql.JSONB(),
        existing_type=sa.JSON(),
        existing_nullable=False,
        postgresql_using="details::jsonb",
    )
    op.execute(
        "CREATE INDEX ix_audit_events_assistant_id "
        "ON audit_events ((details ->> 'assistant_id'))"
    )
    for table, name, condition in _CHECKS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    for table, name, _ in reversed(_CHECKS):
        op.drop_constraint(name, table, type_="check")
    op.execute("DROP INDEX IF EXISTS ix_audit_events_assistant_id")
    op.alter_column(
        "audit_events",
        "details",
        type_=sa.JSON(),
        existing_type=postgresql.JSONB(),
        existing_nullable=False,
        postgresql_using="details::json",
    )
    for name, table, _ in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
