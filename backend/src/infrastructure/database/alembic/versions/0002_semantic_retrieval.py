"""SPEC-002: metadados de indexacao dos documentos e andamento da reindexacao.

Revision ID: 0002_semantic_retrieval
Revises: 0001_baseline
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_semantic_retrieval"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("embedding_model", sa.String(255), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("pipeline_version", sa.String(32), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "documents",
        sa.Column("storage_key", sa.String(512), nullable=True),
    )

    op.create_table(
        "reindex_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "assistant_id",
            sa.String(64),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_collection", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "total_documents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "processed_documents",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_reindex_jobs_assistant_id",
        "reindex_jobs",
        ["assistant_id"],
    )
    # No maximo uma reindexacao em curso por assistente.
    op.create_index(
        "uq_reindex_jobs_running",
        "reindex_jobs",
        ["assistant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("uq_reindex_jobs_running", table_name="reindex_jobs")
    op.drop_index("ix_reindex_jobs_assistant_id", table_name="reindex_jobs")
    op.drop_table("reindex_jobs")
    op.drop_column("documents", "storage_key")
    op.drop_column("documents", "chunk_count")
    op.drop_column("documents", "pipeline_version")
    op.drop_column("documents", "embedding_model")
