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
import ensure_assistant  # noqa: E402
import indexing_time  # noqa: E402
import purge_documents  # noqa: E402
import reindex_under_load  # noqa: E402
import report  # noqa: E402
import ttft  # noqa: E402
import upload_latency  # noqa: E402
import wait_idle  # noqa: E402


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

    def test_reading_the_file_is_not_part_of_the_upload_sample(self) -> None:
        """Ensaio de 2026-10-22: a leitura pela pasta compartilhada gerava picos na RNF-17."""
        (self.dir / "upload-00.pdf").write_bytes(b"%PDF-1.4 a")
        original = upload_latency.prepare

        def slow_prepare(path):
            time.sleep(0.3)
            return original(path)

        upload_latency.prepare = slow_prepare
        self.addCleanup(lambda: setattr(upload_latency, "prepare", original))
        samples = upload_latency.measure(self.base, "a1", "token", [self.dir / "upload-00.pdf"])
        self.assertEqual(samples[0].status, "202")
        self.assertLess(samples[0].duration_s, 0.3)

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

    def test_accepted_limitation_is_reported_but_does_not_fail(self) -> None:
        """PC-D11: a RNF-02 continua medida; a reprovacao aceita nao derruba a V7."""
        slow = report.summarize("indexacao", self._samples([150.0, 220.0], "200"), 60, "all", "PC-D11")
        self.assertEqual(slow.verdict, "reprovado (limitação aceita, PC-D11)")
        broken = report.summarize("indexacao", self._samples([150.0], "timeout"), 60, "all", "PC-D11")
        self.assertEqual(broken.verdict, "reprovado")
        self.assertEqual(report.parse_spec("x.csv:60:all:PC-D11")[1:], (60.0, "all", "PC-D11"))
        self.assertEqual(report.parse_spec("x.csv:3:p95")[1:], (3.0, "p95", None))

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


class PerfTokenAndCorpusTestCase(unittest.TestCase):
    """Ensaio da V7 (2026-10-21): token vencido na espera e arquivos acima do limite."""

    def test_token_source_renews_after_the_interval(self) -> None:
        now = [0.0]
        fetched = iter(["t1", "t2"])
        source = common.TokenSource(fetch=lambda: next(fetched), refresh_seconds=60, clock=lambda: now[0])
        self.assertEqual(source(), "t1")
        now[0] = 59
        self.assertEqual(source(), "t1")
        now[0] = 61
        self.assertEqual(source(), "t2")

    def test_fixed_token_still_accepted(self) -> None:
        self.assertEqual(common.as_token_source("abc")(), "abc")

    def test_upload_files_stay_below_the_ceiling(self) -> None:
        original = corpus.UPLOAD_CEILING
        corpus.UPLOAD_CEILING = 300_000
        self.addCleanup(lambda: setattr(corpus, "UPLOAD_CEILING", original))
        with tempfile.TemporaryDirectory() as directory:
            corpus.main(["--out", directory, "--upload-25mb"])
            sizes = [path.stat().st_size for path in Path(directory).glob("upload-*")]
        self.assertEqual(len(sizes), 2)
        self.assertTrue(all(0.95 * 300_000 <= size <= 300_000 for size in sizes), sizes)

    def test_real_ceiling_is_below_25_mib(self) -> None:
        self.assertLess(corpus.UPLOAD_CEILING, 25 * 1024 * 1024)


class WaitIdleTestCase(unittest.TestCase):
    """RNF-17 com o worker pausado (2026-10-22): a RNF-02 so comeca com a fila vazia."""

    def _patch(self, busy_counts: list[int]) -> list[str]:
        calls: list[str] = []
        original = wait_idle.request

        def fake(method, url, *, headers=None, body=None, timeout=120.0):
            calls.append(headers["Authorization"])
            busy = busy_counts.pop(0)
            items = [{"status": "pendente"}] * busy + [{"status": "indexado"}, {"status": "falhou"}]
            return 200, {}, json.dumps(items).encode()

        wait_idle.request = fake
        self.addCleanup(lambda: setattr(wait_idle, "request", original))
        return calls

    def test_waits_until_no_document_is_pending(self) -> None:
        calls = self._patch([3, 1, 0])
        tokens = iter(["t1", "t2", "t3"])
        sleeps: list[float] = []
        wait_idle.wait_idle(
            "http://api", "a1", wait_minutes=90, token_source=lambda: next(tokens),
            sleep=sleeps.append, clock=lambda: 0.0,
        )
        self.assertEqual(sleeps, [15.0, 15.0])
        self.assertEqual(calls, ["Bearer t1", "Bearer t2", "Bearer t3"])

    def test_gives_up_after_the_wait_limit(self) -> None:
        self._patch([2, 2])
        now = iter([0.0, 0.0, 5401.0])
        with self.assertRaises(SystemExit):
            wait_idle.wait_idle(
                "http://api", "a1", wait_minutes=90, token_source=lambda: "t",
                sleep=lambda _s: None, clock=lambda: next(now),
            )


class EnsureAssistantTestCase(unittest.TestCase):
    """V7 repetida (2026-10-22): a tela nao apaga assistentes; --fresh apaga pela API."""

    def _patch(self) -> list[tuple[str, str]]:
        calls: list[tuple[str, str]] = []
        original = ensure_assistant.request
        listing = json.dumps([{"id": "old", "name": "Desempenho V7"}, {"id": "x", "name": "Outro"}])

        def fake(method, url, *, headers=None, body=None, timeout=120.0):
            calls.append((method, url))
            if method == "GET":
                return 200, {}, listing.encode()
            if method == "DELETE":
                return 204, {}, b""
            return 201, {}, b'{"id": "new"}'

        ensure_assistant.request = fake
        self.addCleanup(lambda: setattr(ensure_assistant, "request", original))
        return calls

    def test_reuses_the_existing_assistant_by_default(self) -> None:
        calls = self._patch()
        self.assertEqual(ensure_assistant.ensure("http://api", "Desempenho V7", "t"), "old")
        self.assertEqual([method for method, _ in calls], ["GET"])

    def test_fresh_deletes_the_old_one_and_creates_another(self) -> None:
        calls = self._patch()
        self.assertEqual(ensure_assistant.ensure("http://api", "Desempenho V7", "t", fresh=True), "new")
        self.assertEqual(
            calls,
            [("GET", "http://api/assistants"), ("DELETE", "http://api/assistants/old"),
             ("POST", "http://api/assistants")],
        )


class IllustratedCorpusTestCase(unittest.TestCase):
    """RNF-02 (decisao do autor, 2026-10-22): 10 MB com texto fixo e o resto em imagens."""

    def setUp(self) -> None:
        original = corpus.INDEX_TEXT_CHARS
        corpus.INDEX_TEXT_CHARS = 20_000
        self.addCleanup(lambda: setattr(corpus, "INDEX_TEXT_CHARS", original))

    def test_fills_the_ceiling_with_images_not_text(self) -> None:
        ceiling = 3 * 1024 * 1024
        with tempfile.TemporaryDirectory() as tmp:
            for maker, name in ((corpus.make_text_pdf, "i.pdf"), (corpus.make_docx, "i.docx")):
                path = corpus.make_illustrated(maker, Path(tmp) / name, ceiling, 7)
                size = path.stat().st_size
                self.assertLessEqual(size, ceiling, name)
                self.assertGreaterEqual(size, 0.98 * ceiling, name)

    def test_text_stays_fixed_and_readable(self) -> None:
        from src.infrastructure.documents import SupportedDocumentExtractor

        extractor = SupportedDocumentExtractor()
        with tempfile.TemporaryDirectory() as tmp:
            for maker, name in ((corpus.make_text_pdf, "i.pdf"), (corpus.make_docx, "i.docx")):
                path = corpus.make_illustrated(maker, Path(tmp) / name, 2 * 1024 * 1024, 8)
                document = extractor.extract(
                    filename=path.name, content_type=None, raw_content=path.read_bytes()
                )
                text = " ".join(block.text for block in document.blocks)
                self.assertGreater(len(text), 15_000, name)
                self.assertLess(len(text), 40_000, name)

    def test_generation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = corpus.make_illustrated(corpus.make_docx, Path(tmp) / "a.docx", 2 * 1024 * 1024, 9)
            first = a.read_bytes()
            b = corpus.make_illustrated(corpus.make_docx, Path(tmp) / "b.docx", 2 * 1024 * 1024, 9)
            self.assertEqual(first, b.read_bytes())


class PurgeDocumentsTestCase(unittest.TestCase):
    """RNF-17 (2026-10-22): os arquivos de 25 MB saem antes de o worker voltar."""

    def test_deletes_every_document_of_the_assistant(self) -> None:
        calls: list[tuple[str, str]] = []
        original = purge_documents.request

        def fake(method, url, *, headers=None, body=None, timeout=120.0):
            calls.append((method, url))
            if method == "GET":
                return 200, {}, json.dumps([{"id": "d1"}, {"id": "d2"}]).encode()
            return (404 if url.endswith("d2") else 204), {}, b""

        purge_documents.request = fake
        self.addCleanup(lambda: setattr(purge_documents, "request", original))
        self.assertEqual(purge_documents.purge("http://api", "a1", "t"), 1)
        self.assertEqual(
            calls,
            [("GET", "http://api/assistants/a1/documents"), ("DELETE", "http://api/documents/d1"),
             ("DELETE", "http://api/documents/d2")],
        )


class TtftAutomationTestCase(unittest.TestCase):
    """RNF-01 na V7 (decisao do autor, 2026-10-22): assistente da V6 e perguntas do escopo."""

    def test_dataset_questions_skip_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "d.jsonl"
            path.write_text(
                json.dumps({"question": "Dentro?", "out_of_scope": False}) + "\n\n"
                + json.dumps({"question": "Fora?", "out_of_scope": True}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(ttft.dataset_questions(str(path)), ["Dentro?"])

    def test_finds_the_v6_assistant_by_name_or_explains(self) -> None:
        original = ttft.request
        listing = json.dumps([{"id": "a9", "name": "Nexus Docs Ampliado (avaliacao)"}]).encode()
        ttft.request = lambda *args, **kwargs: (200, {}, listing)
        self.addCleanup(lambda: setattr(ttft, "request", original))
        self.assertEqual(ttft.find_assistant("http://api", "t", "Nexus Docs Ampliado (avaliacao)"), "a9")
        with self.assertRaises(SystemExit) as raised:
            ttft.find_assistant("http://api", "t", "Outro")
        self.assertIn("V6", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
