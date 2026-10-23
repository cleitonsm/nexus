"""Conferencia de contagens PostgreSQL x Qdrant (R18, decisao PC-D3).

Uso: python -m src.cli.check_consistency [--assistant ID]

So le. Para cada assistente compara os trechos que cada documento deveria ter
na collection vigente com os que o Qdrant guarda, e aponta trechos de
documentos que o PostgreSQL nao conhece. Documentos pendentes ou em
processamento e assistentes em reindexacao ficam de fora. Cada divergencia
sai como um evento ``consistency.divergence`` no log; o resumo, como
``consistency.finished``.

Codigo de saida: 0 sem divergencia; 1 com divergencia; 2 erro de execucao.
A correcao usual e reprocessar ou reenviar o documento, ou reindexar o
assistente (docs/infraestrutura/troubleshooting.md).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from src.application.use_cases import CheckIndexConsistencyUseCase, ConsistencyReport
from src.domain import DomainValidationError
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresDocumentRepository,
    PostgresReindexJobRepository,
    SessionLocal,
)
from src.infrastructure.observability import configure_logging
from src.infrastructure.vector_store import QdrantVectorStoreGateway

EXIT_CONSISTENT = 0
EXIT_DIVERGENT = 1
EXIT_ERROR = 2

logger = logging.getLogger("nexus.consistency")


def _parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m src.cli.check_consistency",
        description="Confere as contagens de trechos entre PostgreSQL e Qdrant (R18).",
    )
    parser.add_argument("--assistant", help="confere apenas este assistente")
    return parser.parse_args(argv)


def report_events(report: ConsistencyReport) -> None:
    for assistant in report.assistants:
        if assistant.skipped_reason:
            logger.info(
                "consistency.skipped",
                extra={
                    "assistant_id": assistant.assistant_id,
                    "reason": assistant.skipped_reason,
                },
            )
            continue
        for item in assistant.divergences:
            logger.warning(
                "consistency.divergence",
                extra={
                    "assistant_id": assistant.assistant_id,
                    "collection": assistant.collection_name,
                    "document_id": item.document_id,
                    "source_name": item.source_name,
                    "status": item.status,
                    "expected_points": item.expected,
                    "found_points": item.found,
                },
            )
        for document_id, count in assistant.orphan_documents:
            logger.warning(
                "consistency.orphan_points",
                extra={
                    "assistant_id": assistant.assistant_id,
                    "collection": assistant.collection_name,
                    "document_id": document_id or None,
                    "found_points": count,
                },
            )
    logger.info(
        "consistency.finished",
        extra={
            "assistants": len(report.assistants),
            "skipped": sum(1 for item in report.assistants if item.skipped_reason),
            "documents_checked": sum(
                item.documents_checked for item in report.assistants
            ),
            "divergences": report.divergence_count,
            "consistent": report.consistent,
        },
    )


def main(argv: list[str] | None = None) -> int:
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    args = _parse(argv)
    try:
        with SessionLocal() as session:
            report = CheckIndexConsistencyUseCase(
                assistant_repository=PostgresAssistantRepository(session=session),
                document_repository=PostgresDocumentRepository(session=session),
                vector_store_gateway=QdrantVectorStoreGateway(
                    url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
                    api_key=os.getenv("QDRANT_API_KEY", "") or None,
                ),
                reindex_job_repository=PostgresReindexJobRepository(session=session),
            ).execute(args.assistant)
    except DomainValidationError as exc:
        logger.error("consistency.invalid", extra={"problem": str(exc)})
        return EXIT_ERROR
    except Exception:  # noqa: BLE001 - banco ou Qdrant indisponivel
        logger.exception("consistency.failed")
        return EXIT_ERROR
    report_events(report)
    return EXIT_CONSISTENT if report.consistent else EXIT_DIVERGENT


if __name__ == "__main__":
    sys.exit(main())
