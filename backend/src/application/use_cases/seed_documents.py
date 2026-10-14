"""Carga dos documentos do piloto para a avaliacao (SPEC-001, ajustada na SPEC-005).

O envio so cria um documento pendente; a indexacao e do worker. O comando de
avaliacao roda sozinho, entao processa a fila aqui, ate esvaziar.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from src.domain import DocumentStatus


class SeedDocumentsError(RuntimeError):
    """Algum documento do piloto nao chegou a ``indexado``."""


def seed_documents(
    directories: Iterable[Path],
    assistant_id: str,
    *,
    upload: Callable[[str, bytes], object],
    process_pending: Callable[[], object | None],
) -> int:
    """Envia os ``*.md`` e ``*.docx`` dos diretorios, processa a fila e confere o resultado.

    ``upload(nome, conteudo)`` devolve o documento pendente (``id`` e
    ``source_name``); ``process_pending()`` devolve um resultado enquanto houver
    job e ``None`` ao esvaziar. Devolve a quantidade de documentos indexados.
    """
    sent = [
        upload(path.name, path.read_bytes())
        for directory in directories
        for path in sorted(
            [*Path(directory).glob("*.md"), *Path(directory).glob("*.docx")]
        )
    ]
    outcomes = []
    while (outcome := process_pending()) is not None:
        outcomes.append(outcome)
    names_by_id = {
        getattr(item, "id", None): getattr(item, "source_name", "?") for item in sent
    }
    failed = [
        names_by_id.get(getattr(item, "document_id", None), "?")
        for item in outcomes
        if getattr(item, "status", None) == DocumentStatus.FAILED.value
    ]
    if failed or len(outcomes) < len(sent):
        names = ", ".join(failed) if failed else "fila nao processada por completo"
        raise SeedDocumentsError(
            f"assistant {assistant_id}: documents not indexed: {names}."
        )
    return len(sent)
