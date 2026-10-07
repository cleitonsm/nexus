"""Ambiente do Alembic: usa a mesma conexao e os mesmos models da aplicacao."""

from __future__ import annotations

from alembic import context  # type: ignore[import-not-found]

from src.infrastructure.database import models  # noqa: F401 - registra as tabelas
from src.infrastructure.database.base import Base
from src.infrastructure.database.session import DATABASE_URL, engine

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
