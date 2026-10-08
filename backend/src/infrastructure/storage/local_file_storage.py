from __future__ import annotations

import re
from pathlib import Path

from src.domain import AssistantId, DocumentId

_UNSAFE = re.compile(r"[^A-Za-z0-9_-]+")
_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


class LocalDocumentFileStorage:
    """Guarda os arquivos originais em um diretorio local (volume do Compose).

    A chave devolvida e o caminho relativo ao diretorio base; o nome informado
    pelo usuario nao participa do caminho, apenas a extensao.
    """

    def __init__(self, *, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir).resolve()

    def save(
        self,
        *,
        assistant_id: AssistantId,
        document_id: DocumentId,
        filename: str,
        content: bytes,
    ) -> str:
        suffix = Path(filename).suffix.lower()
        name = _safe(document_id.value) + (suffix if _SUFFIX.match(suffix) else "")
        key = f"{_safe(assistant_id.value)}/{name}"
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def load(self, storage_key: str) -> bytes:
        path = self._resolve(storage_key)
        if not path.is_file():
            raise FileNotFoundError(f"original file not found: {storage_key}")
        return path.read_bytes()

    def delete(self, storage_key: str) -> None:
        """Remove o original (RN-29); chave sem arquivo nao e erro."""
        self._resolve(storage_key).unlink(missing_ok=True)

    def _resolve(self, storage_key: str) -> Path:
        path = (self._base_dir / storage_key).resolve()
        if not storage_key.strip() or not path.is_relative_to(self._base_dir):
            raise ValueError("invalid storage key.")
        if path == self._base_dir:
            raise ValueError("invalid storage key.")
        return path


def _safe(value: str) -> str:
    cleaned = _UNSAFE.sub("-", value).strip("-")
    if not cleaned:
        raise ValueError("identifier has no valid characters for storage.")
    return cleaned
