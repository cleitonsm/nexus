"""E7: ferramentas de medicao (``scripts/perf``) contra um servidor HTTP falso."""

from __future__ import annotations

import http.server
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PERF = Path(__file__).resolve().parents[3] / "scripts" / "perf"
if not PERF.is_dir():
    # A imagem do backend nao inclui ``scripts/``; o CI e a maquina local sim.
    raise unittest.SkipTest("scripts/perf indisponivel neste ambiente.")
sys.path.insert(0, str(PERF))

import common  # noqa: E402
import corpus  # noqa: E402
import indexing_time  # noqa: E402
import reindex_under_load  # noqa: E402
import report  # noqa: E402
import ttft  # noqa: E402
import upload_latency  # noqa: E402


class FakeApi(http.server.BaseHTTPRequestHandler):
    polls = 0
    uploads: list[bytes] = []

    def log_message(self, *args) -> None:  # silencioso
        pass

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        if self.path.endswith("/documents"):
            FakeApi.uploads.append(body)
            self._json(202, {"id": "doc-1", "status": "pendente"})
        elif self.path == "/conversations":
            self._json(201, {"id": "conv-1"})
        elif self.path.endswith("/chat/stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"event: meta\ndata: {}\n\n")
            self.wfile.flush()
            time.sleep(0.2)
            self.wfile.write(b'event: delta\ndata: {"text": "Ola"}\n\n')
            self.wfile.write(b"event: done\ndata: {}\n\n")
        else:
            self._json(404, {})

    def do_GET(self) -> None:
        if self.path == "/documents/doc-1":
            FakeApi.polls += 1
            state = "indexado" if FakeApi.polls >= 3 else "processando"
            self._json(200, {"id": "doc-1", "status": state})
        else:
            self._json(404, {})


class PerfToolsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeApi)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self) -> None:
        FakeApi.polls = 0
        FakeApi.uploads = []
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.dir = Path(directory.name)

    def test_upload_latency_records_one_sample_per_file(self) -> None:
        (self.dir / "upload-00.pdf").write_bytes(b"%PDF-1.4 a")
        (self.dir / "upload-01.pdf").write_bytes(b"%PDF-1.4 b")
        files = sorted(self.dir.glob("upload-*"))
        samples = upload_latency.measure(self.base, "a1", "token", files)
        self.assertEqual([s.status for s in samples], ["202", "202"])
        self.assertIn(b'filename="upload-00.pdf"', FakeApi.uploads[0])
        self.assertEqual(len({s.request_id for s in samples}), 2)

    def test_indexing_time_waits_for_indexed_state(self) -> None:
        path = self.dir / "index-00.docx"
        path.write_bytes(b"x")
        sample = indexing_time.measure_one(self.base, "a1", "token", path, poll_s=0.01)
        self.assertEqual(sample.status, "200")
        self.assertGreaterEqual(FakeApi.polls, 3)

    def test_ttft_measures_until_first_text_event(self) -> None:
        sample = ttft.ask_timed(self.base, "token", "a1", "Quantos dias de ferias?")
        self.assertEqual(sample.status, "200")
        self.assertGreaterEqual(sample.duration_s, 0.19)
        self.assertLess(sample.duration_s, 5)

    def test_first_text_event_ignores_other_events(self) -> None:
        lines = ["event: meta\n", "data: {}\n", "\n", "event: done\n", "data: {}\n", "\n"]
        self.assertIsNone(ttft.first_text_event_seconds(lines, time.perf_counter()))

    def test_token_comes_from_environment_first(self) -> None:
        self.assertEqual(common.get_token({"NEXUS_TOKEN": "abc"}), "abc")


class ReportTestCase(unittest.TestCase):
    def _samples(self, durations, status="202"):
        return [common.Sample("s", "e", d, status, f"r{i}") for i, d in enumerate(durations)]

    def test_percentiles_use_nearest_rank(self) -> None:
        values = [float(n) for n in range(1, 101)]
        self.assertEqual(common.percentile(values, 0.50), 50.0)
        self.assertEqual(common.percentile(values, 0.95), 95.0)
        self.assertEqual(common.percentile(values, 0.99), 99.0)

    def test_all_rule_fails_when_one_sample_exceeds_the_limit(self) -> None:
        summary = report.summarize("upload", self._samples([1.0] * 29 + [2.5]), 2.0, "all")
        self.assertEqual(summary.verdict, "reprovado")
        self.assertEqual(summary.maximum, 2.5)

    def test_p95_rule_tolerates_one_outlier_in_twenty(self) -> None:
        summary = report.summarize("busca", self._samples([1.0] * 19 + [9.0]), 3.0, "p95")
        self.assertEqual(summary.verdict, "aprovado")

    def test_errors_fail_a_scenario_with_a_criterion(self) -> None:
        samples = self._samples([1.0, 1.0]) + self._samples([1.0], status="500")
        self.assertEqual(report.summarize("x", samples, 2.0).verdict, "reprovado")
        self.assertAlmostEqual(report.summarize("x", samples).error_rate, 1 / 3)

    def test_scenario_without_limit_is_informative(self) -> None:
        self.assertEqual(report.summarize("x", self._samples([9.0])).verdict, "informativo")

    def test_cli_returns_one_on_failure_and_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "upload.csv"
            common.write_samples(csv_path, self._samples([3.0]))
            out = Path(tmp) / "out.md"
            code = report.main([f"{csv_path}:2:all", "--out", str(out)])
            self.assertEqual(code, 1)
            self.assertIn("reprovado", out.read_text(encoding="utf-8"))


class CorpusTestCase(unittest.TestCase):
    def test_generation_is_deterministic_and_files_differ(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            a = corpus.make_docx(base / "a.docx", 30_000, 1)
            b = corpus.make_docx(base / "b.docx", 30_000, 2)
            again = corpus.make_docx(base / "c.docx", 30_000, 1)
            self.assertEqual(a.read_bytes(), again.read_bytes())
            self.assertNotEqual(a.read_bytes(), b.read_bytes())
            self.assertGreaterEqual(a.stat().st_size, 30_000)

    def test_make_fitting_lands_between_95_percent_and_the_ceiling(self) -> None:
        ceiling = 120_000
        with tempfile.TemporaryDirectory() as tmp:
            for maker, name in ((corpus.make_text_pdf, "f.pdf"), (corpus.make_docx, "f.docx")):
                path = corpus.make_fitting(maker, Path(tmp) / name, ceiling, 5)
                size = path.stat().st_size
                self.assertLessEqual(size, ceiling, name)
                self.assertGreaterEqual(size, 0.95 * ceiling, name)

    def test_generated_files_are_readable_by_the_real_extractor(self) -> None:
        from src.infrastructure.documents import SupportedDocumentExtractor

        extractor = SupportedDocumentExtractor()
        with tempfile.TemporaryDirectory() as tmp:
            for path in (
                corpus.make_text_pdf(Path(tmp) / "t.pdf", 20_000, 3),
                corpus.make_docx(Path(tmp) / "t.docx", 20_000, 4),
            ):
                document = extractor.extract(
                    filename=path.name, content_type=None, raw_content=path.read_bytes()
                )
                text = " ".join(block.text for block in document.blocks)
                self.assertGreater(len(text), 5_000, path.name)

    def test_chunks_are_limited_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = corpus.write_chunks(Path(tmp) / "a.jsonl", 50)
            second = corpus.write_chunks(Path(tmp) / "b.jsonl", 50)
            self.assertEqual(first.read_text(), second.read_text())
            self.assertEqual(len(first.read_text().splitlines()), 50)
            with self.assertRaises(ValueError):
                corpus.write_chunks(Path(tmp) / "c.jsonl", 100_001)


class ReindexStartTestCase(unittest.TestCase):
    """RNF-18 (ensaio de 2026-10-21): a API recusa (409) enquanto ha documentos na fila."""

    def _patch(self, statuses: list[int]) -> list[str]:
        calls: list[str] = []
        original = reindex_under_load.request

        def fake(method, url, *, headers=None, body=None, timeout=120.0):
            calls.append(headers["Authorization"])
            status = statuses.pop(0)
            payload = b'{"id": "job-1"}' if status == 202 else b'{"code": "conflict"}'
            return status, {}, payload

        reindex_under_load.request = fake
        self.addCleanup(lambda: setattr(reindex_under_load, "request", original))
        return calls

    def test_waits_while_documents_are_processing(self) -> None:
        calls = self._patch([409, 409, 202])
        tokens = iter(["t1", "t2", "t3"])
        sleeps: list[float] = []
        job = reindex_under_load.start_when_idle(
            "http://api", "a1", wait_minutes=60, token_source=lambda: next(tokens),
            sleep=sleeps.append, clock=lambda: 0.0,
        )
        self.assertEqual(job["id"], "job-1")
        self.assertEqual(sleeps, [15.0, 15.0])
        self.assertEqual(calls, ["Bearer t1", "Bearer t2", "Bearer t3"])  # token novo a cada vez

    def test_gives_up_after_the_wait_limit(self) -> None:
        self._patch([409, 409])
        now = iter([0.0, 0.0, 3601.0])
        with self.assertRaises(SystemExit):
            reindex_under_load.start_when_idle(
                "http://api", "a1", wait_minutes=60, token_source=lambda: "t",
                sleep=lambda _s: None, clock=lambda: next(now),
            )

    def test_other_errors_are_not_retried(self) -> None:
        calls = self._patch([403])
        with self.assertRaises(SystemExit):
            reindex_under_load.start_when_idle(
                "http://api", "a1", wait_minutes=60, token_source=lambda: "t",
                sleep=lambda _s: None, clock=lambda: 0.0,
            )
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
