"""CT-49 (RNF-31): migracoes do banco, para a frente e para tras.

Cria um banco temporario no PostgreSQL do Compose (usa ``DATABASE_URL`` so para
chegar ao servidor) e roda o Alembic em subprocessos apontados para ele. Sem
PostgreSQL, o teste e pulado. Execute dentro do container do backend.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from uuid import uuid4

try:
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
except ImportError:  # pragma: no cover
    sa = None

SCRIPT = """
import sys
from alembic import command
from alembic.config import Config
from src.infrastructure.database.migrate import _SCRIPT_LOCATION

config = Config()
config.set_main_option("script_location", str(_SCRIPT_LOCATION))
action, revision = sys.argv[1], sys.argv[2]
getattr(command, action)(config, revision)
"""


def _admin_engine():
    if sa is None:
        return None
    url = make_url(
        os.getenv(
            "DATABASE_URL", "postgresql+psycopg://nexus:nexus@postgres:5432/nexus"
        )
    ).set(database="postgres")
    engine = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(sa.text("SELECT 1"))
    except Exception:  # noqa: BLE001 - sem servidor, o teste e pulado
        return None
    return engine


class MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = _admin_engine()
        if self.admin is None:
            self.skipTest("PostgreSQL indisponivel")
        self.name = f"nexus_ct49_{uuid4().hex[:10]}"
        with self.admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{self.name}"'))
        self.addCleanup(self._drop)
        base = make_url(
            os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://nexus:nexus@postgres:5432/nexus",
            )
        )
        self.url = base.set(database=self.name)
        self.engine = sa.create_engine(self.url)
        self.addCleanup(self.engine.dispose)

    def _drop(self) -> None:
        self.engine.dispose()
        with self.admin.connect() as connection:
            connection.execute(
                sa.text(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)')
            )
        self.admin.dispose()

    def _alembic(self, action: str, revision: str) -> None:
        env = {
            **os.environ,
            "DATABASE_URL": self.url.render_as_string(hide_password=False),
        }
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, action, revision],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(
            result.returncode, 0, f"{action} {revision}:\n{result.stderr}"
        )

    def _tables(self) -> set[str]:
        return set(sa.inspect(self.engine).get_table_names())

    def test_up_down_up_on_empty_database(self) -> None:
        self._alembic("upgrade", "head")
        after_up = self._tables()
        self.assertIn("assistants", after_up)
        self.assertIn("message_feedback", after_up)
        self._alembic("downgrade", "base")
        self.assertFalse(self._tables() - {"alembic_version"})
        self._alembic("upgrade", "head")
        self.assertEqual(self._tables(), after_up)

    def test_upgrade_preserves_data_from_baseline(self) -> None:
        self._alembic("upgrade", "0001_baseline")
        with self.engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO assistants (id, name) VALUES ('a1', 'Piloto')")
            )
            connection.execute(
                sa.text(
                    "INSERT INTO documents (id, assistant_id, source_name, "
                    "content_hash) VALUES ('d1', 'a1', 'ferias.md', 'h1')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO conversations (id, assistant_id, name) "
                    "VALUES ('c1', 'a1', 'Conversa')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO messages (id, conversation_id, role, content) "
                    "VALUES ('m1', 'c1', 'user', 'Ola')"
                )
            )
        self._alembic("upgrade", "head")
        with self.engine.connect() as connection:
            counts = {
                table: connection.execute(
                    sa.text(f"SELECT count(*) FROM {table}")
                ).scalar_one()
                for table in ("assistants", "documents", "conversations", "messages")
            }
        self.assertEqual(
            counts,
            {"assistants": 1, "documents": 1, "conversations": 1, "messages": 1},
        )

    def test_0008_keeps_audit_rows_append_only_and_makes_details_jsonb(self) -> None:
        """fix-13: json -> jsonb nao pode abrir brecha na trilha (RN-25)."""
        self._alembic("upgrade", "0007_reindex_in_worker")
        with self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO audit_events (id, occurred_at, user_id, action, "
                    "resource_type, details) VALUES ('e1', now(), 'u1', "
                    "'access.denied', 'assistant', '{\"assistant_id\": \"a1\"}')"
                )
            )
        self._alembic("upgrade", "head")
        with self.engine.connect() as connection:
            column = connection.execute(
                sa.text(
                    "SELECT data_type FROM information_schema.columns "
                    "WHERE table_name = 'audit_events' AND column_name = 'details'"
                )
            ).scalar_one()
            found = connection.execute(
                sa.text(
                    "SELECT id FROM audit_events "
                    "WHERE details ->> 'assistant_id' = 'a1'"
                )
            ).scalar_one()
        self.assertEqual(column, "jsonb")
        self.assertEqual(found, "e1")
        with self.engine.connect() as connection:
            with self.assertRaises(sa.exc.DBAPIError):
                connection.execute(sa.text("UPDATE audit_events SET user_id = 'x'"))
        # Volta e sobe de novo: os dados e a protecao sobrevivem aos dois sentidos.
        self._alembic("downgrade", "0007_reindex_in_worker")
        self._alembic("upgrade", "head")
        with self.engine.connect() as connection:
            self.assertEqual(
                connection.execute(
                    sa.text("SELECT count(*) FROM audit_events")
                ).scalar_one(),
                1,
            )
            with self.assertRaises(sa.exc.DBAPIError):
                connection.execute(sa.text("DELETE FROM audit_events"))

    def test_0008_rejects_an_unknown_status(self) -> None:
        self._alembic("upgrade", "head")
        with self.engine.begin() as connection:
            connection.execute(
                sa.text("INSERT INTO assistants (id, name) VALUES ('a1', 'Piloto')")
            )
        with self.engine.connect() as connection:
            with self.assertRaises(sa.exc.IntegrityError):
                connection.execute(
                    sa.text(
                        "INSERT INTO documents (id, assistant_id, source_name, "
                        "content_hash, status) VALUES "
                        "('d1', 'a1', 'x.md', 'h', 'invalido')"
                    )
                )


if __name__ == "__main__":
    unittest.main()
