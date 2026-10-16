"""Reaplica a funcao que protege ``audit_events`` (ambientes com a 0004 antiga).

Revision ID: 0009_reassert_audit_guard
Revises: 0008_indexes_and_constraints

Bancos criados com um rascunho anterior da 0004 ficaram com a funcao que
recusa todo DELETE, sem a excecao da purga de retencao. ``CREATE OR REPLACE``
e idempotente: onde a funcao ja e a correta, nada muda.
"""

from __future__ import annotations

from alembic import op

revision = "0009_reassert_audit_guard"
down_revision = "0008_indexes_and_constraints"
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
    if op.get_bind().dialect.name == "postgresql":
        op.execute(_APPEND_ONLY_FUNCTION)


def downgrade() -> None:
    # Nada a desfazer: a funcao antiga era um defeito, nao um estado desejado.
    pass
