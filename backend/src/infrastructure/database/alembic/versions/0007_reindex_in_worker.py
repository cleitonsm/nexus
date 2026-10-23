"""PC-D4: a reindexacao passa da thread da API para o worker.

O worker reserva o job por um prazo (``lease_expires_at``), renovado a cada
documento; ``attempts`` conta as reservas. Prazo vencido com o job ainda em
curso indica worker interrompido: o job pode ser reservado de novo ate o
limite de tentativas. Jobs em curso de antes desta revisao ficam sem prazo e
sao retomados pelo worker.

Revision ID: 0007_reindex_in_worker
Revises: 0006_operations
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_reindex_in_worker"
down_revision = "0006_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "reindex_jobs",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "reindex_jobs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reindex_jobs", "lease_expires_at")
    op.drop_column("reindex_jobs", "attempts")
