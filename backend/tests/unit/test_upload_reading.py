"""SPEC-007 fix-2: leitura do upload com teto de memoria (413 antecipado)."""

from __future__ import annotations

import asyncio
import unittest

from src.api.uploads import UPLOAD_ENVELOPE_BYTES, read_upload_limited
from src.application.use_cases import DocumentTooLargeError


class FakeUpload:
    def __init__(self, content: bytes) -> None:
        self._content = content
        self.bytes_read = 0

    async def read(self, size: int = -1) -> bytes:
        size = len(self._content) if size < 0 else size
        chunk, self._content = self._content[:size], self._content[size:]
        self.bytes_read += len(chunk)
        return chunk


def run(coro):
    return asyncio.run(coro)


class ReadUploadLimitedTestCase(unittest.TestCase):
    def test_reads_file_within_the_limit(self) -> None:
        upload = FakeUpload(b"a" * 100)
        self.assertEqual(run(read_upload_limited(upload, 100)), b"a" * 100)

    def test_rejects_file_above_the_limit_without_reading_everything(self) -> None:
        upload = FakeUpload(b"a" * 10_000_000)
        with self.assertRaises(DocumentTooLargeError):
            run(read_upload_limited(upload, 100, chunk_size=64))
        self.assertLessEqual(upload.bytes_read, 100 + 64)

    def test_rejects_early_by_declared_content_length(self) -> None:
        upload = FakeUpload(b"a" * 10)
        declared = 100 + UPLOAD_ENVELOPE_BYTES + 1
        with self.assertRaises(DocumentTooLargeError):
            run(read_upload_limited(upload, 100, content_length=declared))
        self.assertEqual(upload.bytes_read, 0)

    def test_ignores_invalid_content_length(self) -> None:
        upload = FakeUpload(b"abc")
        self.assertEqual(
            run(read_upload_limited(upload, 100, content_length=-5)), b"abc"
        )


if __name__ == "__main__":
    unittest.main()
