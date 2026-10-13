"""Janelas de manutencao que suspendem o processamento (SPEC-006 D10)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import DomainValidationError


@dataclass(frozen=True, slots=True)
class IngestionPause:
    """Enquanto ativa, o worker nao reserva jobs de ingestao nem de reindexacao.

    O prazo protege contra um backup interrompido sem liberar a pausa: depois
    dele a ingestao volta sozinha.
    """

    paused_until: datetime
    reason: str = "backup"

    def __post_init__(self) -> None:
        if self.paused_until.tzinfo is None:
            raise DomainValidationError("pause deadline must carry a time zone.")
        if not self.reason.strip():
            raise DomainValidationError("pause reason must not be empty.")

    def is_active(self, now: datetime) -> bool:
        return now < self.paused_until
