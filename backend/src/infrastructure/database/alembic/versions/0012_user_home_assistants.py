"""SPEC-016: acesso rapido a assistentes na tela inicial, por usuario.

Cria ``user_home_assistants``: uma linha por assistente escolhido, com a ordem
de marcacao (D7) e o padrao (RN-47). O banco garante no maximo um padrao por
usuario; o limite de assistentes (D1) fica no dominio, para mudar sem
migracao. Excluir o assistente apaga as linhas (``ON DELETE CASCADE``, D8).

Revision ID: 0012_user_home_assistants
Revises: 0011_drop_global_llm_settings
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0012_user_home_assistants"
down_revision = "0011_drop_global_llm_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_home_assistants",
        # Mesmo tamanho de ``conversations.owner_user_id`` (sub do token).
        sa.Column("owner_user_id", sa.String(128), primary_key=True),
        sa.Column(
            "assistant_id",
            sa.String(64),
            sa.ForeignKey(
                "assistants.id",
                ondelete="CASCADE",
                name="fk_user_home_assistants_assistant_id",
            ),
            primary_key=True,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.CheckConstraint("position >= 0", name="ck_user_home_assistants_position"),
    )
    # A cascata da exclusao do assistente procura por assistant_id.
    op.create_index(
        "ix_user_home_assistants_assistant_id",
        "user_home_assistants",
        ["assistant_id"],
    )
    # RN-47: um padrao por usuario, garantido pelo banco.
    op.create_index(
        "uq_user_home_assistants_single_default",
        "user_home_assistants",
        ["owner_user_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_user_home_assistants_single_default", table_name="user_home_assistants"
    )
    op.drop_index(
        "ix_user_home_assistants_assistant_id", table_name="user_home_assistants"
    )
    op.drop_table("user_home_assistants")
