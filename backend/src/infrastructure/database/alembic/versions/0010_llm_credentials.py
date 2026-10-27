"""SPEC-013: varias credenciais de LLM e configuracao por assistente.

Cria ``llm_credentials`` (uma linha por chave; no maximo uma padrao, RN-37) e
acrescenta em ``assistants`` a credencial escolhida (``ON DELETE RESTRICT``,
RN-38), o modelo e o perfil de recuperacao (D1, D3).

D10: a chave global da SPEC-008 (``secret_settings.global_llm_api_key``) vira a
credencial "Padrão", com o mesmo ciphertext (nada e decifrado aqui) e o
provedor, URL e modelo de ``app_settings.llm_connection``; sem esse registro,
valem ``LLM_API_URL`` e ``LLM_MODEL`` do ambiente, como hoje. Sem chave
gravada, nenhuma credencial e criada. As linhas antigas saem, para a chave nao
ficar guardada em dois lugares; o ``downgrade`` as devolve a partir da
credencial padrao.

Revision ID: 0010_llm_credentials
Revises: 0009_reassert_audit_guard
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0010_llm_credentials"
down_revision = "0009_reassert_audit_guard"
branch_labels = None
depends_on = None

GLOBAL_KEY_NAME = "global_llm_api_key"
CONNECTION_KEY_NAME = "llm_connection"
DEFAULT_CREDENTIAL_NAME = "Padrão"
MIGRATION_AUTHOR = "migration:0010"
# Iguais a ``domain.llm_settings.PROVIDER_ENDPOINTS`` e ao padrao do ambiente;
# copiados porque a migracao nao importa o codigo da aplicacao.
PRESET_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
}
ENVIRONMENT_DEFAULT_MODEL = "gpt-4o-mini"

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
    sa.column("id", sa.String),
    sa.column("name", sa.String),
    sa.column("provider", sa.String),
    sa.column("api_url", sa.String),
    sa.column("models", sa.JSON),
    sa.column("default_model", sa.String),
    sa.column("is_default", sa.Boolean),
    sa.column("encrypted_key", sa.Text),
    sa.column("created_by", sa.String),
    sa.column("updated_by", sa.String),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "llm_credentials",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("api_url", sa.String(2048), nullable=False),
        sa.Column("models", sa.JSON(), nullable=False),
        sa.Column("default_model", sa.String(200), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("encrypted_key", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
        sa.Column("updated_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_llm_credentials_name"),
        sa.CheckConstraint(
            "provider IN ('openai', 'gemini', 'custom')",
            name="ck_llm_credentials_provider",
        ),
    )
    # RN-37: no maximo uma padrao, garantido pelo banco.
    op.create_index(
        "uq_llm_credentials_single_default",
        "llm_credentials",
        ["is_default"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )
    with op.batch_alter_table("assistants") as batch:
        batch.add_column(sa.Column("llm_credential_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("llm_model", sa.String(200), nullable=True))
        batch.add_column(sa.Column("retrieval_profile", sa.JSON(), nullable=True))
        batch.create_foreign_key(
            "fk_assistants_llm_credential_id",
            "llm_credentials",
            ["llm_credential_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    op.create_index(
        "ix_assistants_llm_credential_id", "assistants", ["llm_credential_id"]
    )
    _move_global_key_to_default_credential()


def downgrade() -> None:
    _restore_global_key_from_default_credential()
    op.drop_index("ix_assistants_llm_credential_id", table_name="assistants")
    with op.batch_alter_table("assistants") as batch:
        batch.drop_constraint("fk_assistants_llm_credential_id", type_="foreignkey")
        batch.drop_column("retrieval_profile")
        batch.drop_column("llm_model")
        batch.drop_column("llm_credential_id")
    op.drop_index("uq_llm_credentials_single_default", table_name="llm_credentials")
    op.drop_table("llm_credentials")


def _move_global_key_to_default_credential() -> None:
    bind = op.get_bind()
    ciphertext = bind.execute(
        sa.select(_secret_settings.c.encrypted_value).where(
            _secret_settings.c.key_name == GLOBAL_KEY_NAME
        )
    ).scalar_one_or_none()
    if ciphertext is None:
        return
    stored = bind.execute(
        sa.select(_app_settings.c.value).where(
            _app_settings.c.key_name == CONNECTION_KEY_NAME
        )
    ).scalar_one_or_none()
    provider, api_url, model = _connection(stored)
    now = datetime.now(UTC)
    bind.execute(
        _llm_credentials.insert().values(
            id=uuid4().hex,
            name=DEFAULT_CREDENTIAL_NAME,
            provider=provider,
            api_url=api_url,
            models=[{"name": model, "input_per_1k": None, "output_per_1k": None}],
            default_model=model,
            is_default=True,
            encrypted_key=ciphertext,
            created_by=MIGRATION_AUTHOR,
            updated_by=MIGRATION_AUTHOR,
            created_at=now,
            updated_at=now,
        )
    )
    bind.execute(
        _secret_settings.delete().where(_secret_settings.c.key_name == GLOBAL_KEY_NAME)
    )
    bind.execute(
        _app_settings.delete().where(_app_settings.c.key_name == CONNECTION_KEY_NAME)
    )


def _restore_global_key_from_default_credential() -> None:
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
    bind.execute(
        _secret_settings.delete().where(_secret_settings.c.key_name == GLOBAL_KEY_NAME)
    )
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
        _app_settings.delete().where(_app_settings.c.key_name == CONNECTION_KEY_NAME)
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


def _connection(stored: object) -> tuple[str, str, str]:
    """Provedor, URL e modelo: o gravado pela tela; sem ele, o ambiente."""
    if isinstance(stored, dict):
        try:
            return (
                str(stored["provider"]),
                str(stored["api_url"]),
                str(stored["model"]),
            )
        except KeyError:
            pass
    api_url = os.getenv("LLM_API_URL", "").strip() or PRESET_URLS["openai"]
    model = os.getenv("LLM_MODEL", "").strip()
    if not model or model == "placeholder":
        model = ENVIRONMENT_DEFAULT_MODEL
    provider = next(
        (name for name, url in PRESET_URLS.items() if url == api_url), "custom"
    )
    return provider, api_url, model
