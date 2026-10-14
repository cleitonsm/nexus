"""Leitura de upload com teto de memoria (SPEC-007 fix-2)."""

from __future__ import annotations

from typing import Protocol

from src.application.use_cases import DocumentTooLargeError

UPLOAD_ENVELOPE_BYTES = 64 * 1024
DEFAULT_CHUNK_BYTES = 1024 * 1024


class AsyncReadable(Protocol):
    async def read(self, size: int = -1) -> bytes: ...


async def read_upload_limited(
    file: AsyncReadable,
    max_bytes: int,
    *,
    content_length: int | None = None,
    chunk_size: int = DEFAULT_CHUNK_BYTES,
) -> bytes:
    """Le o arquivo em blocos e levanta 413 ao passar de ``max_bytes``.

    O ``Content-Length`` declarado cobre o arquivo mais o envelope multipart;
    se ja passa do teto somado ao envelope, recusa sem ler nada.
    """
    if content_length is not None and content_length > max_bytes + UPLOAD_ENVELOPE_BYTES:
        raise _too_large(max_bytes)
    received = bytearray()
    while True:
        block = await file.read(min(chunk_size, max_bytes + 1 - len(received)))
        if not block:
            return bytes(received)
        received.extend(block)
        if len(received) > max_bytes:
            raise _too_large(max_bytes)


def parse_content_length(raw: str | None) -> int | None:
    try:
        value = int(raw) if raw is not None else None
    except ValueError:
        return None
    return value if value is not None and value >= 0 else None


def _too_large(max_bytes: int) -> DocumentTooLargeError:
    return DocumentTooLargeError(f"file exceeds the limit of {max_bytes} bytes.")
