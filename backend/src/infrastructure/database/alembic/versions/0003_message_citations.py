"""SPEC-003: fontes gravadas junto da mensagem do assistente.

Revision ID: 0003_message_citations
Revises: 0002_semantic_retrieval
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_message_citations"
down_revision = "0002_semantic_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("citations", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "citations")
