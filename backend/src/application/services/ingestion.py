"""Politica de processamento em segundo plano (SPEC-005, decisao D7)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from src.domain import AuthenticatedUser

# Identidade do worker: e com ela que o resultado do processamento aparece na
# trilha de auditoria (C7).
WORKER_USER = AuthenticatedUser(
    id="system:worker",
    name="Processamento de documentos (worker)",
)

# Motivos exibidos ao curador (C2). O detalhe tecnico fica no log e no job.
UNREADABLE_DOCUMENT_REASON = (
    "Não foi possível extrair texto do arquivo: formato não suportado, "
    "arquivo corrompido ou sem texto reconhecível, mesmo com OCR."
)
OUTDATED_INDEX_REASON = (
    "A base do assistente precisa ser reindexada antes de receber documentos. "
    "Reindexe o assistente e reprocesse o documento."
)
MISSING_ORIGINAL_REASON = (
    "O arquivo original não foi encontrado no armazenamento. "
    "Envie o arquivo novamente."
)
TIMEOUT_REASON = (
    "O processamento excedeu o tempo limite em todas as tentativas. "
    "Reprocesse o documento mais tarde."
)
UNAVAILABLE_SERVICE_REASON = (
    "O processamento falhou em todas as tentativas por indisponibilidade de "
    "um serviço interno. Reprocesse o documento mais tarde."
)


class JobTimeoutError(Exception):
    """O job ficou reservado alem do tempo limite (worker parado ou travado)."""


@dataclass(frozen=True, slots=True)
class IngestionSettings:
    """D7: tres tentativas, esperas de 30 s e 120 s, limite de 600 s por job."""

    max_attempts: int = 3
    retry_delays_seconds: tuple[int, ...] = (30, 120)
    job_timeout_seconds: int = 600

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if self.job_timeout_seconds <= 0:
            raise ValueError("job_timeout_seconds must be positive.")
        if any(delay < 0 for delay in self.retry_delays_seconds):
            raise ValueError("retry delays must not be negative.")

    def delay_after(self, attempt: int) -> timedelta:
        """Espera antes da tentativa seguinte a ``attempt`` (a partir de 1)."""
        if not self.retry_delays_seconds:
            return timedelta(0)
        index = min(max(attempt, 1), len(self.retry_delays_seconds)) - 1
        return timedelta(seconds=self.retry_delays_seconds[index])

    @property
    def job_timeout(self) -> timedelta:
        return timedelta(seconds=self.job_timeout_seconds)
