"""Carga dos documentos do piloto para a avaliacao (SPEC-001, ajustada na SPEC-005).

O envio so cria um documento pendente; a indexacao e do worker. O comando de
avaliacao processa a fila aqui, ate esvaziar. Se o worker da pilha estiver no
ar, ele pode reservar parte dos jobs; os documentos que este processo nao
processou sao acompanhados pelo estado gravado ate chegarem a ``indexado`` ou
``falhou``, com o prazo do job de ingestao (D7, ``INGESTION_JOB_TIMEOUT_SECONDS``).
"""

from __future__ import annotations

import time
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
    current_status: Callable[[str], str | None] | None = None,
    wait_seconds: float = 0.0,
    poll_seconds: float = 3.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Envia os ``*.md``, ``*.txt`` e ``*.docx`` dos diretorios, processa a fila e confere o resultado.

    ``upload(nome, conteudo)`` devolve o documento pendente (``id`` e
    ``source_name``); ``process_pending()`` devolve um resultado enquanto houver
    job e ``None`` ao esvaziar. ``current_status(id)`` devolve o estado gravado
    do documento; com ele, os documentos processados por outro worker sao
    esperados por ate ``wait_seconds``. Devolve a quantidade de documentos indexados.
    """
    sent = [
        upload(path.name, path.read_bytes())
        for directory in directories
        for path in sorted(
            [
                *Path(directory).glob("*.md"),
                *Path(directory).glob("*.txt"),
                *Path(directory).glob("*.docx"),
            ]
        )
    ]
    status_by_id: dict[object, str | None] = {getattr(item, "id", None): None for item in sent}
    _drain(process_pending, status_by_id)
    if current_status is not None:
        _wait_for_other_workers(
            status_by_id, process_pending, current_status,
            wait_seconds, poll_seconds, clock, sleep,
        )
    names_by_id = {
        getattr(item, "id", None): getattr(item, "source_name", "?") for item in sent
    }
    failed = [
        names_by_id.get(document_id, "?")
        for document_id, status in status_by_id.items()
        if status == DocumentStatus.FAILED.value
    ]
    unfinished = [status for status in status_by_id.values() if status not in _TERMINAL]
    if failed or unfinished:
        names = ", ".join(failed) if failed else "fila nao processada por completo"
        raise SeedDocumentsError(
            f"assistant {assistant_id}: documents not indexed: {names}."
        )
    return len(sent)


_TERMINAL = frozenset({DocumentStatus.INDEXED.value, DocumentStatus.FAILED.value})


def _drain(
    process_pending: Callable[[], object | None], status_by_id: dict[object, str | None]
) -> None:
    """Processa os jobs disponiveis e anota o resultado dos documentos enviados."""
    while (outcome := process_pending()) is not None:
        document_id = getattr(outcome, "document_id", None)
        if document_id in status_by_id:
            status_by_id[document_id] = getattr(outcome, "status", None)


def _wait_for_other_workers(
    status_by_id: dict[object, str | None],
    process_pending: Callable[[], object | None],
    current_status: Callable[[str], str | None],
    wait_seconds: float,
    poll_seconds: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> None:
    """Acompanha os documentos ainda abertos ate todos terminarem ou o prazo vencer.

    A cada volta processa os jobs que ficaram disponiveis (nova tentativa, D7)
    e le o estado gravado dos que outro worker reservou.
    """
    deadline = clock() + max(wait_seconds, 0.0)
    while True:
        _drain(process_pending, status_by_id)
        for document_id, status in status_by_id.items():
            if status not in _TERMINAL:
                status_by_id[document_id] = current_status(str(document_id))
        if all(status in _TERMINAL for status in status_by_id.values()):
            return
        if clock() >= deadline:
            return
        sleep(poll_seconds)
