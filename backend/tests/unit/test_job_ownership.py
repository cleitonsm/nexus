"""SPEC-007 fix-3: renovacao da reserva e checagem de dono dos jobs (dois workers)."""

from __future__ import annotations

from datetime import timedelta

from test_indexing import IndexingTestCase

from src.application.use_cases import (
    RequeueExpiredIngestionJobsUseCase,
    RunReindexInput,
    RunReindexUseCase,
)
from src.domain import IngestionJobStatus, JobOwnershipLostError, ReindexStatus


class IngestionOwnershipTestCase(IndexingTestCase):
    def _requeue(self):
        s = self.scenario
        return RequeueExpiredIngestionJobsUseCase(
            job_queue=s.queue,
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            access_control=s.access.control,
            clock=s.clock,
        ).execute()

    def _take_over(self):
        """Outro worker assume o job depois de a reserva expirar."""
        s = self.scenario
        s.clock.advance(seconds=601)
        self._requeue()
        s.clock.advance(seconds=31)  # espera da nova tentativa (D7)
        return s.queue.reserve_next(s.clock())

    def test_renew_keeps_a_long_job_from_being_requeued(self) -> None:
        s = self.scenario
        s.upload()
        job = s.queue.reserve_next(s.clock())
        s.clock.advance(seconds=400)
        self.assertTrue(s.queue.renew(job, s.clock()))
        s.clock.advance(seconds=400)
        self.assertEqual(self._requeue(), [])

    def test_renew_is_refused_after_another_worker_took_the_job(self) -> None:
        s = self.scenario
        s.upload()
        stale = s.queue.reserve_next(s.clock())
        fresh = self._take_over()
        self.assertEqual(fresh.attempts, 2)
        self.assertFalse(s.queue.renew(stale, s.clock()))
        self.assertTrue(s.queue.renew(fresh, s.clock()))

    def test_stale_worker_cannot_write_the_result(self) -> None:
        s = self.scenario
        s.upload()
        stale = s.queue.reserve_next(s.clock())
        self._take_over()
        document = s.documents.get_by_id(stale.document_id)
        for write in (
            lambda: s.queue.complete(stale.complete(), document),
            lambda: s.queue.retry(stale.retry_at(s.clock(), "x"), document),
            lambda: s.queue.fail(stale.fail("x"), document),
        ):
            with self.assertRaises(JobOwnershipLostError):
                write()
        self.assertEqual(s.queue.jobs[stale.id].attempts, 2)
        self.assertEqual(s.queue.jobs[stale.id].status, IngestionJobStatus.PROCESSING)

    def test_worker_that_lost_the_job_stops_without_touching_the_document(self) -> None:
        s = self.scenario
        s.upload()
        original_build = s.indexer.build_chunks

        def build_while_another_worker_takes_over(**kwargs):
            chunks = original_build(**kwargs)
            self._take_over()
            return chunks

        s.indexer.build_chunks = build_while_another_worker_takes_over

        outcome = s.process()

        self.assertIsNone(outcome)
        job = next(iter(s.queue.jobs.values()))
        self.assertEqual((job.attempts, job.status), (2, IngestionJobStatus.PROCESSING))
        self.assertEqual(s.vector_store.collections.get("assistant-a1-v1", {}), {})


class ReindexOwnershipTestCase(IndexingTestCase):
    lease = timedelta(seconds=60)

    def _run(self, job_id: str, attempts_lease=None):
        s = self.scenario
        return RunReindexUseCase(
            document_repository=s.documents,
            vector_store_gateway=s.vector_store,
            document_indexer=s.indexer,
            file_storage=s.storage,
            reindex_job_repository=s.jobs,
            permission_repository=s.access.permissions,
            lease=self.lease,
            clock=s.clock,
        ).execute(RunReindexInput(job_id=job_id))

    def test_renew_lease_requires_the_same_attempt(self) -> None:
        s = self.scenario
        s.ingest(document_id="doc-1")
        started = s.start_reindex()
        s.jobs.claim_next(s.clock(), self.lease)
        until = s.clock() + self.lease
        self.assertTrue(
            s.jobs.renew_lease(started.id, 1, lease_expires_at=until, processed_documents=0)
        )
        self.assertFalse(
            s.jobs.renew_lease(started.id, 2, lease_expires_at=until, processed_documents=0)
        )

    def test_worker_that_lost_the_lease_does_not_swap_or_discard(self) -> None:
        s = self.scenario
        s.ingest(document_id="doc-1")
        started = s.start_reindex()
        s.jobs.claim_next(s.clock(), self.lease)  # worker A: tentativa 1
        original_load = s.storage.load
        taken = []

        def load_while_another_worker_takes_over(key):
            if not taken:
                s.clock.advance(seconds=61)
                taken.append(s.jobs.claim_next(s.clock(), self.lease))  # B: tentativa 2
                # B ja preparou a collection de destino.
                s.vector_store.collections["assistant-a1-v2"] = {"do-b": object()}
            return original_load(key)

        s.storage.load = load_while_another_worker_takes_over

        self._run(started.id)

        self.assertEqual(taken[0].attempts, 2)
        job = s.jobs.items[started.id]
        self.assertEqual((job.status, job.attempts), (ReindexStatus.RUNNING, 2))
        self.assertEqual(s.vector_store.aliases, {"assistant-a1": "assistant-a1-v1"})
        self.assertIn("do-b", s.vector_store.collections["assistant-a1-v2"])
