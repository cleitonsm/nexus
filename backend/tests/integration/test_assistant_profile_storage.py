"""CT-135 (SPEC-017): ``update_profile`` no PostgreSQL.

Mesmo arranjo do CT-126: banco temporario no PostgreSQL do Compose e Alembic
em subprocesso. Sem PostgreSQL, o teste e pulado. Execute dentro do container
do backend.
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
    from sqlalchemy.orm import Session
except ImportError:  # pragma: no cover
    sa = None

from src.domain import Assistant, AssistantId, AssistantName, RetrievalProfile


class AssistantProfileStorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.admin = _admin_engine()
        if self.admin is None:
            self.skipTest("PostgreSQL indisponivel")
        self.name = f"nexus_ct135_{uuid4().hex[:10]}"
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

    def _repository(self):
        from src.infrastructure.database import PostgresAssistantRepository

        env = {**os.environ, "DATABASE_URL": self.url.render_as_string(hide_password=False)}
        result = subprocess.run(
            [sys.executable, "-c", SCRIPT, "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        session = Session(self.engine)
        self.addCleanup(session.close)
        return PostgresAssistantRepository(session=session)

    def test_updates_only_the_three_columns(self) -> None:
        repository = self._repository()
        repository.save(
            Assistant(
                id=AssistantId("juridico"),
                name=AssistantName("Assistente juridico"),
                description="Contratos",
                initial_prompt="Aja como advogado.",
            )
        )
        repository.update_retrieval_profile(AssistantId("juridico"), RetrievalProfile(top_k=8))

        updated = repository.update_profile(
            AssistantId("juridico"),
            name=AssistantName("Juridico e Contratos"),
            description=None,
            initial_prompt="Responda em topicos.",
        )

        self.assertIsNotNone(updated)
        loaded = repository.get_by_id(AssistantId("juridico"))
        self.assertEqual(loaded.name.value, "Juridico e Contratos")
        self.assertIsNone(loaded.description)
        self.assertEqual(loaded.initial_prompt, "Responda em topicos.")
        # Perfil gravado antes continua (sem atualizacao perdida).
        self.assertEqual(loaded.retrieval_profile, RetrievalProfile(top_k=8))

    def test_missing_assistant_returns_none_and_creates_nothing(self) -> None:
        repository = self._repository()
        result = repository.update_profile(
            AssistantId("nao-existe"),
            name=AssistantName("Fantasma"),
            description=None,
            initial_prompt=None,
        )
        self.assertIsNone(result)
        self.assertEqual(repository.list_all(), [])


if __name__ == "__main__":
    unittest.main()
