"""fix-10 e fix-11: timeout das ferramentas e classificacao das falhas."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from src.application.use_cases.process_ingestion import _definitive_reason
from src.application.services import (
    OUTDATED_INDEX_REASON,
    UNREADABLE_DOCUMENT_REASON,
)
from src.domain import (
    IndexOutdatedError,
    TransientServiceError,
    UnreadableDocumentError,
)
from src.infrastructure.documents import text_extraction
from src.infrastructure.documents.ocr import TesseractPdfOcr


class ToolTimeoutTest(unittest.TestCase):
    def test_run_tool_turns_timeout_into_transient_error(self) -> None:
        expired = subprocess.TimeoutExpired(cmd="antiword", timeout=1)
        with mock.patch.object(subprocess, "run", side_effect=expired):
            with self.assertRaises(TransientServiceError):
                text_extraction._run_tool(["antiword", "x.doc"], timeout=1)

    def test_run_tool_passes_the_timeout(self) -> None:
        done = subprocess.CompletedProcess(["x"], 0, stdout="ok", stderr="")
        with mock.patch.object(subprocess, "run", return_value=done) as run:
            result = text_extraction._run_tool(["x"], timeout=7)
        self.assertEqual(result.stdout, "ok")
        self.assertEqual(run.call_args.kwargs["timeout"], 7)

    def test_all_doc_extractors_use_the_timeout(self) -> None:
        expired = subprocess.TimeoutExpired(cmd="x", timeout=1)
        from pathlib import Path

        with (
            mock.patch.object(text_extraction.shutil, "which", return_value="/bin/x"),
            mock.patch.object(subprocess, "run", side_effect=expired),
        ):
            for runner in (
                text_extraction._run_antiword,
                text_extraction._run_catdoc,
                text_extraction._run_libreoffice_convert,
            ):
                with self.assertRaises(TransientServiceError, msg=runner.__name__):
                    runner(Path("a.doc"), Path("."))

    def test_ocr_timeout_is_transient_and_failure_is_unreadable(self) -> None:
        ocr = TesseractPdfOcr(timeout_seconds=1)
        expired = subprocess.TimeoutExpired(cmd="tesseract", timeout=1)
        with mock.patch.object(subprocess, "run", side_effect=expired):
            with self.assertRaises(TransientServiceError):
                ocr._run(["tesseract", "a.png"])
        failed = subprocess.CalledProcessError(1, "tesseract", stderr=b"boom")
        with mock.patch.object(subprocess, "run", side_effect=failed):
            with self.assertRaises(UnreadableDocumentError):
                ocr._run(["tesseract", "a.png"])


class FailureClassificationTest(unittest.TestCase):
    def test_unreadable_document_is_definitive(self) -> None:
        self.assertEqual(
            _definitive_reason(UnreadableDocumentError("corrupt")),
            UNREADABLE_DOCUMENT_REASON,
        )

    def test_plain_value_error_stays_definitive(self) -> None:
        self.assertEqual(
            _definitive_reason(ValueError("empty")), UNREADABLE_DOCUMENT_REASON
        )

    def test_transient_error_is_retried(self) -> None:
        self.assertIsNone(_definitive_reason(TransientServiceError("slow")))

    def test_outdated_index_is_still_definitive(self) -> None:
        self.assertEqual(
            _definitive_reason(IndexOutdatedError("x")), OUTDATED_INDEX_REASON
        )


if __name__ == "__main__":
    unittest.main()
