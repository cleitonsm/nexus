"""SPEC-006 D10: a pausa gravada por scripts/backup.sh e lida pelo worker.

Exige o PostgreSQL do Compose (execute dentro do container do backend). O SQL
abaixo e o mesmo de ``pause_ingestion`` em ``scripts/backup-common.sh``: se um
mudar, o outro tambem precisa mudar.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

PAUSE_SQL = """
INSERT INTO app_settings (key_name, value, updated_by, updated_at)
VALUES ('ingestion_pause',
        json_build_object('paused_until', now() + make_interval(secs => :seconds),
                          'reason', 'backup'),
        'backup', now())
ON CONFLICT (key_name) DO UPDATE
SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = now()
"""
RESUME_SQL = "DELETE FROM app_settings WHERE key_name = 'ingestion_pause'"


def _database_session():
    """Sessao no PostgreSQL com as migracoes aplicadas, ou None."""
    try:
        from sqlalchemy import text

        from src.infrastructure.database import SessionLocal, run_migrations

        run_migrations()
        session = SessionLocal()
        session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - banco indisponivel pula o teste
        return None
    return session


class IngestionPauseStorageTestCase(unittest.TestCase):
    def setUp(self) -> None:
        session = _database_session()
        if session is None:
            self.skipTest("PostgreSQL indisponivel")
        from sqlalchemy import text

        from src.infrastructure.database import PostgresIngestionPauseRepository

        self.text = text
        self.session = session
        self.addCleanup(session.close)
        self.addCleanup(self._resume)
        self.repository = PostgresIngestionPauseRepository(session=session)

    def _resume(self) -> None:
        self.session.execute(self.text(RESUME_SQL))
        self.session.commit()

    def _pause(self, seconds: int) -> None:
        self.session.execute(self.text(PAUSE_SQL), {"seconds": seconds})
        self.session.commit()

    def test_pause_written_by_the_backup_script_is_read_by_the_worker(self) -> None:
        self._pause(600)
        pause = self.repository.current()
        self.assertIsNotNone(pause)
        self.assertTrue(pause.is_active(datetime.now(UTC)))
        self.assertEqual(pause.reason, "backup")

    def test_released_pause_lets_the_worker_run(self) -> None:
        self._pause(600)
        self._resume()
        self.assertIsNone(self.repository.current())

    def test_expired_pause_is_not_active(self) -> None:
        self._pause(-1)
        self.assertFalse(self.repository.current().is_active(datetime.now(UTC)))


if __name__ == "__main__":
    unittest.main()
