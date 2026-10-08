"""Worker de ingestao e de reindexacao (SPEC-005, ADR 0009, PC-D4).

Uso: python -m src.cli.worker
Mesma imagem e mesmo codigo do backend, outro comando de entrada. Consome a
fila ``ingestion_jobs`` e, quando ela esta vazia, as reindexacoes pedidas
(``reindex_jobs``), ate receber SIGTERM ou SIGINT; o trabalho em andamento e
concluido antes de sair. Se o processo for encerrado no meio de um job, o job
volta a fila depois de ``INGESTION_JOB_TIMEOUT_SECONDS`` (D7); uma reindexacao
interrompida e retomada do zero depois do mesmo prazo, contado a partir do
ultimo documento processado.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from src.application.services import (
    AccessControl,
    AuditTrail,
    DocumentIndexer,
    IngestionSettings,
)
from src.application.use_cases import (
    ProcessNextIngestionJobUseCase,
    ProcessNextReindexJobUseCase,
    ReindexSettings,
    RequeueExpiredIngestionJobsUseCase,
    RunReindexInput,
    RunReindexUseCase,
)
from src.domain import DocumentFileStorage, VectorStoreGateway
from src.infrastructure.composition import (
    build_document_indexer,
    build_file_storage,
    default_sparse_encoding_parameters,
    ingestion_settings,
    reindex_settings,
)
from src.infrastructure.database import (
    PostgresAssistantPermissionRepository,
    PostgresAuditLogRepository,
    PostgresDocumentRepository,
    PostgresIndexParametersRepository,
    PostgresIngestionJobQueue,
    PostgresReindexJobRepository,
    SessionLocal,
)
from src.infrastructure.observability import configure_logging
from src.infrastructure.vector_store import QdrantVectorStoreGateway

EXIT_OK = 0
EXIT_INVALID_CONFIGURATION = 2
# Espera entre consultas quando a fila esta vazia (C9).
IDLE_POLL_SECONDS = 2.0

logger = logging.getLogger("nexus.worker")


@dataclass(frozen=True, slots=True)
class WorkerAdapters:
    """Adaptadores carregados uma vez por processo (o modelo de embedding e caro)."""

    vector_store: VectorStoreGateway
    indexer: DocumentIndexer
    storage: DocumentFileStorage
    settings: IngestionSettings
    reindex: ReindexSettings


def run_once(session: Session, adapters: WorkerAdapters) -> bool:
    """Devolve jobs vencidos a fila e processa um job; indica se havia job."""
    documents = PostgresDocumentRepository(session=session)
    queue = PostgresIngestionJobQueue(session=session)
    access_control = AccessControl(
        permission_repository=PostgresAssistantPermissionRepository(session=session),
        audit_trail=AuditTrail(PostgresAuditLogRepository(session=session)),
    )
    RequeueExpiredIngestionJobsUseCase(
        job_queue=queue,
        document_repository=documents,
        vector_store_gateway=adapters.vector_store,
        access_control=access_control,
        settings=adapters.settings,
    ).execute()
    outcome = ProcessNextIngestionJobUseCase(
        job_queue=queue,
        document_repository=documents,
        vector_store_gateway=adapters.vector_store,
        document_indexer=adapters.indexer,
        file_storage=adapters.storage,
        reindex_job_repository=PostgresReindexJobRepository(session=session),
        access_control=access_control,
        settings=adapters.settings,
        index_parameters=PostgresIndexParametersRepository(
            session=session,
            assumed_when_missing=default_sparse_encoding_parameters(),
        ),
    ).execute()
    return outcome is not None


def run_reindex_once(session: Session, adapters: WorkerAdapters) -> bool:
    """PC-D4: reserva e executa uma reindexacao; indica se havia alguma."""
    index_parameters = PostgresIndexParametersRepository(
        session=session,
        assumed_when_missing=default_sparse_encoding_parameters(),
    )
    jobs = PostgresReindexJobRepository(session=session)

    def run(job_id: str, lease: timedelta):
        return RunReindexUseCase(
            document_repository=PostgresDocumentRepository(session=session),
            vector_store_gateway=adapters.vector_store,
            document_indexer=adapters.indexer,
            file_storage=adapters.storage,
            reindex_job_repository=jobs,
            permission_repository=PostgresAssistantPermissionRepository(
                session=session
            ),
            index_parameters=index_parameters,
            lease=lease,
        ).execute(RunReindexInput(job_id=job_id))

    result = ProcessNextReindexJobUseCase(
        reindex_job_repository=jobs,
        vector_store_gateway=adapters.vector_store,
        run_reindex=run,
        settings=adapters.reindex,
    ).execute()
    if result is not None:
        logger.info(
            "reindex.worker.finished",
            extra={"job_id": result.id, "status": result.status},
        )
    return result is not None


def main() -> int:
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    try:
        adapters = WorkerAdapters(
            vector_store=QdrantVectorStoreGateway(
                url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
                api_key=os.getenv("QDRANT_API_KEY", "") or None,
            ),
            indexer=build_document_indexer(),
            storage=build_file_storage(),
            settings=ingestion_settings(),
            reindex=reindex_settings(),
        )
    except ValueError as exc:
        logger.error("ingestion.worker.invalid", extra={"problem": str(exc)})
        return EXIT_INVALID_CONFIGURATION

    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    logger.info(
        "ingestion.worker.started",
        extra={
            "max_attempts": adapters.settings.max_attempts,
            "job_timeout_seconds": adapters.settings.job_timeout_seconds,
        },
    )
    while not stop.is_set():
        try:
            with SessionLocal() as session:
                found = run_once(session, adapters)
            if not found:
                with SessionLocal() as session:
                    found = run_reindex_once(session, adapters)
        except Exception:  # noqa: BLE001 - o worker nao pode parar por um job
            logger.exception("ingestion.worker.iteration_failed")
            found = False
        if not found:
            stop.wait(IDLE_POLL_SECONDS)
    logger.info("ingestion.worker.stopped")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
