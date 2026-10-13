"""SPEC-006 D10: o backup pausa a ingestao pelo banco (cenario "Backup sem escrita concorrente")."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from src.application.services import ingestion_paused
from src.domain import DomainValidationError, IngestionPause

NOW = datetime(2026, 10, 13, 3, 0, tzinfo=UTC)


class StoredPause:
    def __init__(self, pause: IngestionPause | None) -> None:
        self.pause = pause

    def current(self) -> IngestionPause | None:
        return self.pause


class IngestionPauseTestCase(unittest.TestCase):
    def test_pause_is_active_until_its_deadline(self) -> None:
        pause = IngestionPause(paused_until=NOW + timedelta(minutes=30), reason="backup")
        self.assertTrue(pause.is_active(NOW))
        self.assertFalse(pause.is_active(NOW + timedelta(minutes=30)))

    def test_deadline_must_carry_a_time_zone(self) -> None:
        with self.assertRaises(DomainValidationError):
            IngestionPause(paused_until=datetime(2026, 10, 13, 3, 0))

    def test_reason_must_not_be_empty(self) -> None:
        with self.assertRaises(DomainValidationError):
            IngestionPause(paused_until=NOW, reason=" ")


class IngestionPausedTestCase(unittest.TestCase):
    def test_no_stored_pause_lets_the_worker_run(self) -> None:
        self.assertFalse(ingestion_paused(StoredPause(None), NOW))

    def test_active_pause_stops_the_worker(self) -> None:
        pause = IngestionPause(paused_until=NOW + timedelta(seconds=1))
        self.assertTrue(ingestion_paused(StoredPause(pause), NOW))

    def test_expired_pause_is_ignored(self) -> None:
        """Backup morto sem liberar a pausa nao trava a ingestao para sempre."""
        pause = IngestionPause(paused_until=NOW - timedelta(seconds=1))
        self.assertFalse(ingestion_paused(StoredPause(pause), NOW))


if __name__ == "__main__":
    unittest.main()
