from __future__ import annotations

from pathlib import Path

_SCRIPT_LOCATION = Path(__file__).resolve().parent / "alembic"


def run_migrations(revision: str = "head") -> None:
    """Aplica as migracoes versionadas ate a revisao indicada (ADR 0011)."""
    from alembic import command  # type: ignore[import-not-found]
    from alembic.config import Config  # type: ignore[import-not-found]

    config = Config()
    config.set_main_option("script_location", str(_SCRIPT_LOCATION))
    command.upgrade(config, revision)
