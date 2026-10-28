"""CT-126 (SPEC-016): migracao 0012 e repositorio do acesso rapido no PostgreSQL.

Mesmo arranjo do CT-49 (``test_migrations``): banco temporario no PostgreSQL do
Compose e Alembic em subprocesso. Sem PostgreSQL, o teste e pulado. Execute
dentro do container do backend.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from uuid import uuid4

from test_migrations import SCRIPT, _admin_engine

try:
    import sqlalchemy as sa
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover
    sa = None

from src.domain import Assistant, AssistantId, AssistantName, HomeAssistantSelection


def _selection(ids: tuple[str, ...], default: str) -> HomeAssistantSelection:
    return HomeAssistantSelection(
        assistant_ids=tuple(AssistantId(item) for item in ids),
        default_id=AssistantId(default),
    )


class HomeAssistantsStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = _admin_engine()
        if self.admin is None:
            self.skipTest("PostgreSQL indisponivel")
        self.name = f"nexus_ct126_{uuid4().hex[:10]}"
        with self.admin.connect() as connection:
            connection.execute(sa.text(f'CREATE DATABASE "{self.name}"'))
        self.addCleanup(self._drop)
        base = make_url(
            os.getenv("DATABASE_URL", "postgresql+psycopg://nexus:nexus@postgres:5432/nexus")
        )
        self.url = base.set(database=self.name)
        self.engine = sa.create_engine(self.url)
        self.addCleanup(self.engine.dispose)

    def _drop(self) -> None:
        self.engine.dispose()
        with self.admin.connect() as connection:
            connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{self.name}" WITH (FORCE)'))
        self.admin.dispose()

    def _alembic(self, action: str, revision: str) -> None:
        env = {**os.environ, "DATABASE_URL": self.url.render_as_string(hide_password=False)}
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, action, revision],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, f"{action} {revision}:\n{result.stderr}")

    def _ready(self, *assistant_ids: str):
        from src.infrastructure.database import (
            PostgresAssistantRepository,
            PostgresHomeAssistantPreferenceRepository,
        )

        self._alembic("upgrade", "head")
        session = Session(self.engine)
        self.addCleanup(session.close)
        assistants = PostgresAssistantRepository(session=session)
        for assistant_id in assistant_ids:
            assistants.save(
                Assistant(id=AssistantId(assistant_id), name=AssistantName(assistant_id))
            )
        return session, assistants, PostgresHomeAssistantPreferenceRepository(session)

    def test_migration_goes_up_and_down(self) -> None:
        self._alembic("upgrade", "head")
        inspector = sa.inspect(self.engine)
        self.assertIn("user_home_assistants", inspector.get_table_names())
        self._alembic("downgrade", "0011_drop_global_llm_settings")
        self.assertNotIn("user_home_assistants", sa.inspect(self.engine).get_table_names())

    def test_round_trip_keeps_order_and_default(self) -> None:
        _, _, repository = self._ready("a", "b", "c")
        self.assertIsNone(repository.get("ana"))
        repository.replace("ana", _selection(("c", "a", "b"), "a"))
        saved = repository.get("ana")
        self.assertEqual(saved, _selection(("c", "a", "b"), "a"))

    def test_replace_swaps_the_whole_selection(self) -> None:
        _, _, repository = self._ready("a", "b", "c")
        repository.replace("ana", _selection(("a", "b"), "b"))
        repository.replace("ana", _selection(("c",), "c"))
        self.assertEqual(repository.get("ana"), _selection(("c",), "c"))

    def test_users_are_isolated(self) -> None:
        _, _, repository = self._ready("a", "b")
        repository.replace("ana", _selection(("a",), "a"))
        repository.replace("bruno", _selection(("b",), "b"))
        self.assertEqual(repository.get("ana"), _selection(("a",), "a"))
        self.assertEqual(repository.get("bruno"), _selection(("b",), "b"))

    def test_database_refuses_two_defaults(self) -> None:
        self._ready("a", "b")
        with self.assertRaises(IntegrityError), self.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO user_home_assistants (owner_user_id, assistant_id, position, "
                    "is_default) VALUES ('ana', 'a', 0, true), ('ana', 'b', 1, true)"
                )
            )

    def test_deleting_assistant_cascades(self) -> None:
        """D8: a exclusao (SPEC-014) apaga a linha; o padrao perdido cai no primeiro."""
        _, assistants, repository = self._ready("a", "b")
        repository.replace("ana", _selection(("a", "b"), "a"))
        assistants.delete(AssistantId("a"))
        self.assertEqual(repository.get("ana"), _selection(("b",), "b"))


if __name__ == "__main__":
    unittest.main()
