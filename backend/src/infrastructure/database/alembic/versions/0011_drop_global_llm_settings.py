"""SPEC-013 (D9, T9): apaga a chave global e a conexao da SPEC-008.

A 0010 copiou ``secret_settings.global_llm_api_key`` e
``app_settings.llm_connection`` para a credencial "Padrão". Com o chat lendo
so as credenciais (P4) e as rotas antigas removidas (P5), as linhas antigas
sairiam de uso e a chave ficaria guardada em dois lugares. As tabelas ficam:
``secret_settings`` e ``app_settings`` continuam disponiveis para outros usos.

O ``downgrade`` recria as duas linhas a partir da credencial padrao vigente,
para o codigo da SPEC-008 voltar a funcionar.

Revision ID: 0011_drop_global_llm_settings
Revises: 0010_llm_credentials
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0011_drop_global_llm_settings"
down_revision = "0010_llm_credentials"
branch_labels = None
depends_on = None

GLOBAL_KEY_NAME = "global_llm_api_key"
CONNECTION_KEY_NAME = "llm_connection"
MIGRATION_AUTHOR = "migration:0011"

_secret_settings = sa.table(
    "secret_settings",
    sa.column("key_name", sa.String),
    sa.column("encrypted_value", sa.Text),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
_app_settings = sa.table(
    "app_settings",
    sa.column("key_name", sa.String),
    sa.column("value", sa.JSON),
    sa.column("updated_by", sa.String),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)
_llm_credentials = sa.table(
    "llm_credentials",
    sa.column("provider", sa.String),
    sa.column("api_url", sa.String),
    sa.column("default_model", sa.String),
    sa.column("is_default", sa.Boolean),
    sa.column("encrypted_key", sa.Text),
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        _secret_settings.delete().where(_secret_settings.c.key_name == GLOBAL_KEY_NAME)
    )
    bind.execute(
        _app_settings.delete().where(_app_settings.c.key_name == CONNECTION_KEY_NAME)
    )


def downgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(
        sa.select(
            _llm_credentials.c.provider,
            _llm_credentials.c.api_url,
            _llm_credentials.c.default_model,
            _llm_credentials.c.encrypted_key,
        ).where(_llm_credentials.c.is_default.is_(True))
    ).first()
    if row is None:
        return
    now = datetime.now(UTC)
    if row.encrypted_key:
        bind.execute(
            _secret_settings.insert().values(
                key_name=GLOBAL_KEY_NAME,
                encrypted_value=row.encrypted_key,
                created_at=now,
                updated_at=now,
            )
        )
    bind.execute(
        _app_settings.insert().values(
            key_name=CONNECTION_KEY_NAME,
            value={
                "provider": row.provider,
                "model": row.default_model,
                "api_url": row.api_url,
            },
            updated_by=MIGRATION_AUTHOR,
            updated_at=now,
        )
    )
