"""SPEC-018: resumidor de documentos (ADR 0014).

- ``assistants.system_kind``: marca o assistente de sistema (RN-55), unico por
  tipo, e cria o "Resumidor de documentos" com id fixo (T6), sem grupo e sem
  credencial (segue a padrao, ADR 0013).
- ``documents``: dono, conversa e expiracao do documento pessoal (RN-58, D9);
  status ``expirado`` para a lapide (T7); no maximo um documento por conversa
  (D8), garantido pelo banco; conversa so com dono.
- ``document_summaries`` e ``document_summary_sections``: andamento, resumo
  consolidado e mini-resumos (D30, D36).
- ``usage_records.operation``: separa o uso do resumo das perguntas (RN-65);
  as linhas antigas viram ``chat``.

``ingestion_jobs.kind`` nao tem CHECK: o novo valor ``resumo`` (D21) nao muda o
esquema.

Revision ID: 0013_document_summarizer
Revises: 0012_user_home_assistants
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_document_summarizer"
down_revision = "0012_user_home_assistants"
branch_labels = None
depends_on = None

# Copiados de ``domain/document_summary.py`` na data da migracao: a migracao
# nao importa o dominio, que pode mudar depois.
_SUMMARIZER_ID = "system-document-summarizer"
_SUMMARIZER_KIND = "document_summarizer"
_SUMMARIZER_NAME = "Resumidor de documentos"
_SUMMARIZER_DESCRIPTION = (
    "Resume documentos Word, PDF e texto enviados por você e responde perguntas "
    "sobre eles."
)

_OLD_DOCUMENT_STATUS = (
    "status IN ('pendente', 'processando', 'indexado', 'falhou', 'substituido')"
)
_NEW_DOCUMENT_STATUS = (
    "status IN ('pendente', 'processando', 'indexado', 'falhou', 'substituido', "
    "'expirado')"
)
_SUMMARY_STAGES = (
    "stage IN ('enviado', 'extraindo', 'indexando', 'resumindo', 'pronto', "
    "'falhou', 'expirado')"
)
_USAGE_OPERATIONS = "operation IN ('chat', 'document_summary')"


def upgrade() -> None:
    _upgrade_assistants()
    _upgrade_documents()
    _create_summary_tables()
    op.add_column(
        "usage_records",
        sa.Column(
            "operation", sa.String(32), nullable=False, server_default="chat"
        ),
    )
    op.create_check_constraint(
        "ck_usage_records_operation", "usage_records", _USAGE_OPERATIONS
    )


def _upgrade_assistants() -> None:
    op.add_column(
        "assistants", sa.Column("system_kind", sa.String(32), nullable=True)
    )
    op.create_index(
        "uq_assistants_system_kind",
        "assistants",
        ["system_kind"],
        unique=True,
        postgresql_where=sa.text("system_kind IS NOT NULL"),
    )
    # Idempotente: rodar de novo nao duplica o resumidor.
    op.get_bind().execute(
        sa.text(
            "INSERT INTO assistants (id, name, description, initial_prompt, "
            "created_at, system_kind) "
            "VALUES (:id, :name, :description, NULL, now(), :kind) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {
            "id": _SUMMARIZER_ID,
            "name": _SUMMARIZER_NAME,
            "description": _SUMMARIZER_DESCRIPTION,
            "kind": _SUMMARIZER_KIND,
        },
    )


def _upgrade_documents() -> None:
    op.add_column(
        "documents", sa.Column("owner_user_id", sa.String(128), nullable=True)
    )
    op.add_column(
        "documents",
        sa.Column(
            "conversation_id",
            sa.String(64),
            sa.ForeignKey(
                "conversations.id",
                ondelete="SET NULL",
                name="fk_documents_conversation_id",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint("ck_documents_status", "documents", _NEW_DOCUMENT_STATUS)
    op.create_check_constraint(
        "ck_documents_conversation_owner",
        "documents",
        "conversation_id IS NULL OR owner_user_id IS NOT NULL",
    )
    # D8: um documento por conversa; tambem atende a busca por conversa.
    op.create_index(
        "uq_documents_conversation_id",
        "documents",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("conversation_id IS NOT NULL"),
    )
    # T8: cota diaria por usuario.
    op.create_index(
        "ix_documents_owner_created",
        "documents",
        ["owner_user_id", "created_at"],
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
    )
    # T9: limpeza dos vencidos.
    op.create_index(
        "ix_documents_personal_expires_at",
        "documents",
        ["expires_at"],
        postgresql_where=sa.text(
            "owner_user_id IS NOT NULL AND status <> 'expirado'"
        ),
    )


def _create_summary_tables() -> None:
    op.create_table(
        "document_summaries",
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey(
                "documents.id",
                ondelete="CASCADE",
                name="fk_document_summaries_document_id",
            ),
            primary_key=True,
        ),
        sa.Column("stage", sa.String(16), nullable=False),
        sa.Column("batches_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("batches_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("document_tokens", sa.Integer(), nullable=True),
        sa.Column("prompt_version", sa.String(16), nullable=True),
        sa.Column("model", sa.String(200), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(_SUMMARY_STAGES, name="ck_document_summaries_stage"),
        sa.CheckConstraint(
            "batches_done >= 0 AND batches_done <= batches_total",
            name="ck_document_summaries_batches",
        ),
    )
    op.create_table(
        "document_summary_sections",
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey(
                "document_summaries.document_id",
                ondelete="CASCADE",
                name="fk_document_summary_sections_document_id",
            ),
            primary_key=True,
        ),
        sa.Column("position", sa.SmallInteger(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "position >= 0", name="ck_document_summary_sections_position"
        ),
    )


def downgrade() -> None:
    op.drop_constraint("ck_usage_records_operation", "usage_records", type_="check")
    op.drop_column("usage_records", "operation")
    op.drop_table("document_summary_sections")
    op.drop_table("document_summaries")
    bind = op.get_bind()
    # Documentos pessoais nao existiam antes; a lapide violaria o CHECK antigo.
    bind.execute(sa.text("DELETE FROM documents WHERE owner_user_id IS NOT NULL"))
    op.drop_index("ix_documents_personal_expires_at", table_name="documents")
    op.drop_index("ix_documents_owner_created", table_name="documents")
    op.drop_index("uq_documents_conversation_id", table_name="documents")
    op.drop_constraint("ck_documents_conversation_owner", "documents", type_="check")
    op.drop_constraint("ck_documents_status", "documents", type_="check")
    op.create_check_constraint("ck_documents_status", "documents", _OLD_DOCUMENT_STATUS)
    op.drop_column("documents", "expires_at")
    op.drop_constraint("fk_documents_conversation_id", "documents", type_="foreignkey")
    op.drop_column("documents", "conversation_id")
    op.drop_column("documents", "owner_user_id")
    # Conversas e documentos do resumidor saem pela cascata.
    bind.execute(
        sa.text("DELETE FROM assistants WHERE system_kind IS NOT NULL")
    )
    op.drop_index("uq_assistants_system_kind", table_name="assistants")
    op.drop_column("assistants", "system_kind")
