"""SPEC-005: estado e versao dos documentos e fila de processamento.

Documentos ja gravados estavam indexados (a ingestao era sincrona): ficam no
estado ``indexado``, versao 1 (C3). Os gravados antes da Fase 2 nao tem
arquivo original e so voltam a ser processados com novo envio (risco R9).

O indice de ``(assistant_id, content_hash)`` nao e unico: bases anteriores a
RN-26 podem ter o mesmo arquivo mais de uma vez. A duplicidade e verificada
pela aplicacao a cada envio.

Revision ID: 0005_document_lifecycle
Revises: 0004_access_control
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_document_lifecycle"
down_revision = "0004_access_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="indexado",
        ),
    )
    op.add_column("documents", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("documents", sa.Column("size_bytes", sa.BigInteger(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "documents",
        sa.Column(
            "replaces_document_id",
            sa.String(64),
            sa.ForeignKey(
                "documents.id",
                name="fk_documents_replaces_document_id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "documents", sa.Column("uploaded_by", sa.String(255), nullable=True)
    )
    op.create_index(
        "ix_documents_assistant_hash",
        "documents",
        ["assistant_id", "content_hash"],
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_ingestion_jobs_document_id", "ingestion_jobs", ["document_id"]
    )
    op.create_index(
        "ix_ingestion_jobs_status_available",
        "ingestion_jobs",
        ["status", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_jobs_status_available", table_name="ingestion_jobs")
    op.drop_index("ix_ingestion_jobs_document_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_documents_assistant_hash", table_name="documents")
    op.drop_column("documents", "uploaded_by")
    op.drop_constraint(
        "fk_documents_replaces_document_id", "documents", type_="foreignkey"
    )
    op.drop_column("documents", "replaces_document_id")
    op.drop_column("documents", "version")
    op.drop_column("documents", "size_bytes")
    op.drop_column("documents", "attempts")
    op.drop_column("documents", "failure_reason")
    op.drop_column("documents", "status")
