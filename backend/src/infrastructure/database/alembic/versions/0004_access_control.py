"""SPEC-004: grupos de assistentes e de documentos, dono da conversa e auditoria.

Dados anteriores a autenticacao nao sao alterados: assistentes ficam sem
grupo (visiveis so a administradores, RN-22) e conversas ficam sem dono
(arquivadas, nao exibidas a ninguem).

A tabela ``audit_events`` e somente de inclusao (RN-25): um gatilho recusa
UPDATE, DELETE e TRUNCATE mesmo para quem acessa o banco pela aplicacao. A unica
excecao e a limpeza por retencao (D6): DELETE dentro de uma transacao que ligou
``nexus.audit_purge`` com ``SET LOCAL``, o que so o comando de manutencao faz.

Revision ID: 0004_access_control
Revises: 0003_message_citations
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_access_control"
down_revision = "0003_message_citations"
branch_labels = None
depends_on = None

_APPEND_ONLY_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_events_append_only() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE'
       AND current_setting('nexus.audit_purge', true) = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.create_table(
        "assistant_groups",
        sa.Column(
            "assistant_id",
            sa.String(64),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("group_name", sa.String(255), primary_key=True),
    )
    op.create_table(
        "document_groups",
        sa.Column(
            "document_id",
            sa.String(64),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("group_name", sa.String(255), primary_key=True),
    )

    op.add_column(
        "conversations",
        sa.Column("owner_user_id", sa.String(128), nullable=True),
    )
    op.create_index(
        "ix_conversations_owner_user_id",
        "conversations",
        ["owner_user_id"],
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(_APPEND_ONLY_FUNCTION)
        op.execute(
            "CREATE TRIGGER audit_events_no_change "
            "BEFORE UPDATE OR DELETE ON audit_events "
            "FOR EACH ROW EXECUTE FUNCTION audit_events_append_only()"
        )
        op.execute(
            "CREATE TRIGGER audit_events_no_truncate "
            "BEFORE TRUNCATE ON audit_events "
            "FOR EACH STATEMENT EXECUTE FUNCTION audit_events_append_only()"
        )


def downgrade() -> None:
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_table("audit_events")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION IF EXISTS audit_events_append_only()")
    op.drop_index("ix_conversations_owner_user_id", table_name="conversations")
    op.drop_column("conversations", "owner_user_id")
    op.drop_table("document_groups")
    op.drop_table("assistant_groups")
