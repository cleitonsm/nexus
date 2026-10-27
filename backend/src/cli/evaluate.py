"""Comando de avaliacao do pipeline de RAG (SPEC-20261007-001).

Uso: python -m src.cli.evaluate --dataset <arquivo.jsonl> --reports-dir <dir>
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from src.application.use_cases import (
    CompareEvaluationReportsInput,
    CompareEvaluationReportsUseCase,
    CreateAssistantInput,
    CreateAssistantUseCase,
    EvaluateAssistantInput,
    EvaluateAssistantUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
    ProcessNextIngestionJobUseCase,
    SeedDocumentsError,
    seed_documents,
)
from src.application.services import (
    PIPELINE_VERSION,
    AccessControl,
    AssistantRuntime,
    AuditTrail,
    ContextRetriever,
    GroundedAnswerGenerator,
    ResolvedLLM,
    RetrievalSettings,
    build_assistant_runtime,
    is_index_outdated,
    read_index_state,
)
from src.domain import (
    AssistantId,
    AuthenticatedUser,
    DocumentId,
    DocumentRepository,
    EmbeddingGateway,
    EvaluationItem,
    LLMGateway,
    Role,
    VectorStoreGateway,
)
from src.infrastructure.composition import (
    bm25_parameters,
    build_document_indexer,
    build_embedding_gateway,
    llm_connection_defaults,
    llm_timeout_seconds,
    build_file_storage,
    build_reranker_gateway,
    build_sparse_embedding_gateway,
    build_token_counter,
    default_sparse_encoding_parameters,
    ingestion_settings,
    max_file_bytes,
    reranker_model_name,
    retrieval_settings,
    usage_settings,
)
from src.infrastructure.database import (
    PostgresAssistantPermissionRepository,
    PostgresAssistantRepository,
    PostgresAuditLogRepository,
    PostgresDocumentRepository,
    PostgresIndexParametersRepository,
    PostgresIngestionJobQueue,
    PostgresReindexJobRepository,
    SessionLocal,
    run_migrations,
)
from src.infrastructure.database.llm_credential_repository import (
    PostgresLLMCredentialRepository,
)
from src.infrastructure.evaluation import (
    EvaluationDatasetError,
    JsonEvaluationReportStore,
    JsonlEvaluationDatasetLoader,
    LLMAnswerJudge,
)
from src.infrastructure.llm import HttpChatCompletionsLLM
from src.infrastructure.observability import configure_logging
from src.infrastructure.secrets import FernetSecretCipher
from src.infrastructure.vector_store import QdrantVectorStoreGateway

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_INVALID_DATASET = 2
EXIT_SEED_FAILED = 3


# O comando roda no servidor, sem token: age como uma identidade de sistema,
# e e com esse identificador que as acoes dele aparecem na auditoria.
EVALUATION_USER = AuthenticatedUser(
    id="system:evaluation",
    name="Avaliacao (linha de comando)",
    roles=frozenset({Role.ADMIN}),
)

_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)

logger = logging.getLogger("nexus.evaluation")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    configure_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    try:
        items = JsonlEvaluationDatasetLoader(
            allow_unvalidated=args.allow_unvalidated
        ).load(args.dataset)
    except EvaluationDatasetError as exc:
        for problem in exc.errors:
            logger.error("evaluation.dataset.invalid", extra={"problem": problem})
        return EXIT_INVALID_DATASET

    run_migrations()
    with SessionLocal() as session:
        return _run(args, items, session)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Avalia o pipeline de RAG.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--reports-dir", type=Path, required=True)
    parser.add_argument("--assistant-name", default="Nexus Docs (avaliacao)")
    parser.add_argument("--seed-dir", type=Path, action="append", default=[])
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-generation", action="store_true")
    parser.add_argument("--allow-unvalidated", action="store_true")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=float(os.getenv("EVAL_REGRESSION_TOLERANCE", "0.02")),
    )
    return parser.parse_args(argv)


def _run(
    args: argparse.Namespace,
    items: list[EvaluationItem],
    session: Session,
) -> int:
    embedding_gateway = build_embedding_gateway()
    vector_store_gateway = QdrantVectorStoreGateway(
        url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        api_key=os.getenv("QDRANT_API_KEY", "") or None,
    )
    document_repository = PostgresDocumentRepository(session=session)
    access_control = AccessControl(
        permission_repository=PostgresAssistantPermissionRepository(
            session=session
        ),
        audit_trail=AuditTrail(PostgresAuditLogRepository(session=session)),
    )
    assistant_id = _ensure_assistant(args, session, access_control)
    _discard_outdated_index(
        assistant_id,
        document_repository,
        vector_store_gateway,
        embedding_gateway,
    )
    indexer = build_document_indexer()
    storage = build_file_storage()
    queue = PostgresIngestionJobQueue(session=session)
    reindex_jobs = PostgresReindexJobRepository(session=session)
    try:
        _seed_documents(
            args.seed_dir,
            assistant_id,
            ingest=IngestDocumentUseCase(
                document_repository=document_repository,
                vector_store_gateway=vector_store_gateway,
                document_indexer=indexer,
                file_storage=storage,
                job_queue=queue,
                max_file_bytes=max_file_bytes(),
                access_control=access_control,
            ),
            process_next=ProcessNextIngestionJobUseCase(
                job_queue=queue,
                document_repository=document_repository,
                vector_store_gateway=vector_store_gateway,
                document_indexer=indexer,
                file_storage=storage,
                reindex_job_repository=reindex_jobs,
                access_control=access_control,
                index_parameters=PostgresIndexParametersRepository(
                    session=session,
                    assumed_when_missing=default_sparse_encoding_parameters(),
                ),
            ),
            document_repository=document_repository,
            session=session,
        )
    except SeedDocumentsError as exc:
        logger.error("evaluation.seed.failed", extra={"problem": str(exc)})
        return EXIT_SEED_FAILED

    # SPEC-013 (RF-95): a mesma configuracao que o chat usaria para o assistente.
    runtime = _assistant_runtime(session, assistant_id)
    llm_gateway = None if args.no_generation else _generation_gateway(runtime)
    settings = runtime.retrieval
    report = EvaluateAssistantUseCase(
        document_repository=document_repository,
        context_retriever=ContextRetriever(
            embedding_gateway=embedding_gateway,
            sparse_embedding_gateway=build_sparse_embedding_gateway(),
            vector_store_gateway=vector_store_gateway,
            reranker_gateway=build_reranker_gateway(),
            settings=settings,
        ),
        token_counter=build_token_counter(),
        answer_generator=(
            GroundedAnswerGenerator(llm_gateway=llm_gateway)
            if llm_gateway
            else None
        ),
        answer_judge=(
            LLMAnswerJudge(llm_gateway=llm_gateway) if llm_gateway else None
        ),
    ).execute(
        EvaluateAssistantInput(
            assistant_id=assistant_id.value,
            items=tuple(items),
            k=args.k,
            parameters=_parameters(
                args, embedding_gateway, llm_gateway, settings, runtime
            ),
        )
    )
    return _store_and_compare(args, report.to_dict(), report.metrics)


def _ensure_assistant(
    args: argparse.Namespace,
    session: Session,
    access_control: AccessControl,
) -> AssistantId:
    repository = PostgresAssistantRepository(session=session)
    for assistant in repository.list_all():
        if assistant.name.value == args.assistant_name:
            return assistant.id
    created = CreateAssistantUseCase(repository, access_control).execute(
        CreateAssistantInput(
            user=EVALUATION_USER,
            name=args.assistant_name,
            description="Assistente piloto usado na avaliacao de qualidade.",
        )
    )
    logger.info("evaluation.assistant.created", extra={"assistant_id": created.id})
    return AssistantId(created.id)


def _discard_outdated_index(
    assistant_id: AssistantId,
    document_repository: DocumentRepository,
    vector_store_gateway: VectorStoreGateway,
    embedding_gateway: EmbeddingGateway,
) -> None:
    """Descarta a base do piloto gerada por outro modelo ou pipeline.

    O piloto e sempre reconstruido a partir dos diretorios de origem, entao
    nao depende dos arquivos originais nem da rotina de reindexacao.
    """
    documents = document_repository.list_by_assistant(assistant_id)
    state = read_index_state(vector_store_gateway, assistant_id)
    outdated = is_index_outdated(
        state,
        documents,
        embedding_model=embedding_gateway.model_name,
        pipeline_version=PIPELINE_VERSION,
    )
    if not outdated and all(document.is_indexed for document in documents):
        return
    for collection in (state.current, state.alias if state.legacy else None):
        if collection is not None:
            vector_store_gateway.delete_collection(collection)
    for document in documents:
        document_repository.delete(document.id)
    logger.info(
        "evaluation.index.discarded",
        extra={"assistant_id": assistant_id.value, "documents": len(documents)},
    )


def _seed_content_type(name: str) -> str:
    lowered = name.lower()
    if lowered.endswith(".docx"):
        return _DOCX_CONTENT_TYPE
    if lowered.endswith(".txt"):
        return "text/plain"
    return "text/markdown"


def _seed_documents(
    seed_directories: list[Path],
    assistant_id: AssistantId,
    *,
    ingest: IngestDocumentUseCase,
    process_next: ProcessNextIngestionJobUseCase,
    document_repository: PostgresDocumentRepository,
    session: Session,
) -> None:
    """Indexa os documentos do piloto apenas quando a base esta vazia.

    Com o worker da pilha no ar, parte dos jobs pode ser dele: o estado desses
    documentos e lido do banco ate o prazo do job de ingestao (D7).
    """
    if document_repository.list_by_assistant(assistant_id):
        return

    def upload(name: str, content: bytes):
        return ingest.execute(
            IngestDocumentInput(
                user=EVALUATION_USER,
                assistant_id=assistant_id.value,
                source_name=name,
                raw_content=content,
                content_type=_seed_content_type(name),
            )
        )

    def current_status(document_id: str) -> str | None:
        session.expire_all()  # o worker grava em outra sessao
        document = document_repository.get_by_id(DocumentId(document_id))
        return document.status.value if document else None

    indexed = seed_documents(
        seed_directories,
        assistant_id.value,
        upload=upload,
        process_pending=process_next.execute,
        current_status=current_status,
        wait_seconds=ingestion_settings().job_timeout_seconds,
    )
    logger.info("evaluation.documents.seeded", extra={"documents": indexed})


def _assistant_runtime(session: Session, assistant_id: AssistantId) -> AssistantRuntime:
    assistant = PostgresAssistantRepository(session=session).get_by_id(assistant_id)
    if assistant is None:  # pragma: no cover - _ensure_assistant acabou de garantir
        raise RuntimeError("evaluation assistant not found.")
    return build_assistant_runtime(
        assistant,
        base_settings=retrieval_settings(),
        credentials=PostgresLLMCredentialRepository(session=session),
        cipher=_cipher(),
        environment=llm_connection_defaults(),
        currency=usage_settings().pricing.currency,
        gateway_builder=_http_gateway,
    )


class _NoSecretsKey:
    """Sem ``NEXUS_SECRETS_KEY`` nao ha como decifrar: segue sem geracao."""

    def encrypt(self, plaintext: str) -> str:  # pragma: no cover - nao usado aqui
        raise RuntimeError("NEXUS_SECRETS_KEY is not set.")

    def decrypt(self, ciphertext: str) -> str:
        return ""


def _cipher() -> FernetSecretCipher | _NoSecretsKey:
    master_key = os.getenv("NEXUS_SECRETS_KEY", "")
    return FernetSecretCipher(master_key=master_key) if master_key.strip() else _NoSecretsKey()


class _MissingCredentialLLM:
    """Sem chave: a avaliacao roda sem geracao (aviso no log)."""

    model = "nao utilizado"


def _http_gateway(resolved: ResolvedLLM) -> LLMGateway:
    if not resolved.api_key:
        return _MissingCredentialLLM()  # type: ignore[return-value]
    return HttpChatCompletionsLLM(
        api_url=resolved.connection.api_url,
        model=resolved.connection.model,
        api_key=resolved.api_key,
        timeout_seconds=llm_timeout_seconds(),
    )


def _generation_gateway(runtime: AssistantRuntime) -> LLMGateway | None:
    if not runtime.llm.api_key:
        logger.warning("evaluation.generation.skipped", extra={"reason": "no_llm_credential"})
        return None
    return runtime.llm_gateway


def _parameters(
    args: argparse.Namespace,
    embedding_gateway: EmbeddingGateway,
    llm_gateway: LLMGateway | None,
    settings: RetrievalSettings,
    runtime: AssistantRuntime,
) -> dict[str, str]:
    return {
        "commit": os.getenv("GIT_COMMIT", "unknown"),
        "dataset": args.dataset.name,
        "embedding": embedding_gateway.model_name,
        "embedding_vector_size": str(embedding_gateway.dimension),
        "pipeline_version": PIPELINE_VERSION,
        "chunk_max_tokens": os.getenv("CHUNK_MAX_TOKENS", "").strip()
        or "limite do modelo",
        "chunk_overlap_sentences": os.getenv("CHUNK_OVERLAP_SENTENCES", "1"),
        "chunk_prefix_max_tokens": os.getenv("CHUNK_PREFIX_MAX_TOKENS", "32"),
        "sparse": "bm25 (idf no Qdrant), fusao RRF",
        "bm25": ", ".join(
            f"{name}={value}" for name, value in bm25_parameters().items()
        ),
        "reranker": reranker_model_name(),
        "retrieval_candidates": str(settings.candidates),
        "rerank_top_n": str(settings.top_n),
        "retrieval_hybrid": "sim" if settings.hybrid_enabled else "nao (so densa)",
        "relevance_min_score": str(settings.min_score),
        "context_token_budget": str(settings.context_token_budget),
        "history_token_budget": str(settings.history_token_budget),
        "structural_context_token_budget": str(
            settings.structural_context_token_budget
        ),
        "llm_model": runtime.llm.connection.model if llm_gateway else "nao utilizado",
        # SPEC-013 (RF-95): de onde vieram o LLM e os parametros.
        "llm_source": runtime.llm.source.value,
        "llm_credential": runtime.llm.credential_name or "ambiente",
        "llm_model_fell_back": "sim" if runtime.llm.model_fell_back else "nao",
        "judge": "LLMAnswerJudge" if llm_gateway else "nao utilizado",
        "tolerance": str(args.tolerance),
    }


def _store_and_compare(
    args: argparse.Namespace,
    report: dict[str, object],
    metrics: dict[str, float | None],
) -> int:
    store = JsonEvaluationReportStore(args.reports_dir)
    dataset_name = args.dataset.stem
    previous = store.load_latest(dataset_name)
    comparison = CompareEvaluationReportsUseCase().execute(
        CompareEvaluationReportsInput(
            current=metrics,
            previous=previous["metrics"] if previous else None,
            tolerance=args.tolerance,
        )
    )
    commit = os.getenv("GIT_COMMIT", "unknown")
    label = f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{commit}"
    path = store.save(
        dataset_name,
        report,
        label=label,
        deltas=comparison.deltas,
        regressions=comparison.regressions,
    )
    logger.info(
        "evaluation.finished",
        extra={
            **{name: value for name, value in metrics.items()},
            "report": str(path),
            "regressions": ",".join(comparison.regressions) or "nenhuma",
            "validated": report["validated"],
        },
    )
    return EXIT_REGRESSION if comparison.has_regression else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
