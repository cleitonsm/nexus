"""Limpeza da trilha de auditoria por retencao (SPEC-004, D6; RNF-24).

Uso: python -m src.cli.purge_audit
Apaga os eventos mais antigos que ``AUDIT_RETENTION_DAYS`` (padrao 365) e
registra a propria limpeza na trilha. A API nao oferece essa operacao.
"""

from __future__ import annotations

import logging
import os
import sys

from src.application.services import AuditTrail
from src.application.use_cases import PurgeAuditEventsInput, PurgeAuditEventsUseCase
from src.domain import DomainValidationError
from src.infrastructure.composition import audit_retention_days
from src.infrastructure.database import (
    PostgresAuditLogRepository,
    PostgresAuditRetentionRepository,
    SessionLocal,
    run_migrations,
)
from src.infrastructure.observability import configure_logging

EXIT_OK = 0
EXIT_INVALID_CONFIGURATION = 2

logger = logging.getLogger("nexus.audit")


def main() -> int:
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    try:
        retention_days = audit_retention_days()
    except ValueError as exc:
        logger.error("audit.purge.invalid", extra={"problem": str(exc)})
        return EXIT_INVALID_CONFIGURATION
    run_migrations()
    with SessionLocal() as session:
        use_case = PurgeAuditEventsUseCase(
            retention_repository=PostgresAuditRetentionRepository(session=session),
            audit_trail=AuditTrail(PostgresAuditLogRepository(session=session)),
        )
        try:
            result = use_case.execute(
                PurgeAuditEventsInput(retention_days=retention_days)
            )
        except DomainValidationError as exc:
            logger.error("audit.purge.invalid", extra={"problem": str(exc)})
            return EXIT_INVALID_CONFIGURATION
    logger.info(
        "audit.purge.finished",
        extra={
            "removed": result.removed,
            "older_than": result.cutoff.isoformat(),
            "retention_days": retention_days,
        },
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
