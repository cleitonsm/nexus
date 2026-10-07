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
    GetGlobalApiKeyValueUseCase,
    IngestDocumentInput,
    IngestDocumentUseCase,
)
from src.application.services import (
    PIPELINE_VERSION,
    is_index_outdated,
    read_index_state,
)
from src.domain import (
    AssistantId,
    DocumentRepository,
    EmbeddingGateway,
    EvaluationItem,
    LLMGateway,
    VectorStoreGateway,
)
from src.infrastructure.composition import (
    build_document_indexer,
    build_embedding_gateway,
    build_file_storage,
    max_file_bytes,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresDocumentRepository,
    PostgresReindexJobRepository,
    PostgresSecretSettingsRepository,
    SessionLocal,
    run_migrations,
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

DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_API_URL = "https://api.openai.com/v1/chat/completions"

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
    parser.add_argument("--context-top-k", type=int, default=4)
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
    assistant_id = _ensure_assistant(args, session)
    _discard_outdated_index(
        assistant_id,
        document_repository,
        vector_store_gateway,
        embedding_gateway,
    )
    _seed_documents(
        args.seed_dir,
        assistant_id,
        IngestDocumentUseCase(
            document_repository=document_repository,
            vector_store_gateway=vector_store_gateway,
            document_indexer=build_document_indexer(),
            file_storage=build_file_storage(),
            reindex_job_repository=PostgresReindexJobRepository(session=session),
            max_file_bytes=max_file_bytes(),
        ),
        document_repository,
    )

    llm_gateway = None if args.no_generation else _build_llm_gateway(session)
    report = EvaluateAssistantUseCase(
        document_repository=document_repository,
        embedding_gateway=embedding_gateway,
        vector_store_gateway=vector_store_gateway,
        llm_gateway=llm_gateway,
        answer_judge=(
            LLMAnswerJudge(llm_gateway=llm_gateway) if llm_gateway else None
        ),
    ).execute(
        EvaluateAssistantInput(
            assistant_id=assistant_id.value,
            items=tuple(items),
            k=args.k,
            context_top_k=args.context_top_k,
            parameters=_parameters(args, embedding_gateway, llm_gateway),
        )
    )
    return _store_and_compare(args, report.to_dict(), report.metrics)


def _ensure_assistant(args: argparse.Namespace, session: Session) -> AssistantId:
    repository = PostgresAssistantRepository(session=session)
    for assistant in repository.list_all():
        if assistant.name.value == args.assistant_name:
            return assistant.id
    created = CreateAssistantUseCase(repository).execute(
        CreateAssistantInput(
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


def _seed_documents(
    seed_directories: list[Path],
    assistant_id: AssistantId,
    ingest: IngestDocumentUseCase,
    document_repository: PostgresDocumentRepository,
) -> None:
    """Indexa os documentos do piloto apenas quando a base esta vazia."""
    if document_repository.list_by_assistant(assistant_id):
        return
    for directory in seed_directories:
        for path in sorted(directory.glob("*.md")):
            result = ingest.execute(
                IngestDocumentInput(
                    assistant_id=assistant_id.value,
                    source_name=path.name,
                    raw_content=path.read_bytes(),
                    content_type="text/markdown",
                )
            )
            logger.info(
                "evaluation.document.seeded",
                extra={"source_name": path.name, "chunks": result.chunk_count},
            )


def _build_llm_gateway(session: Session) -> LLMGateway | None:
    credential = GetGlobalApiKeyValueUseCase(
        secret_repository=PostgresSecretSettingsRepository(session=session),
        secret_cipher=FernetSecretCipher(
            master_key=os.getenv("NEXUS_SECRETS_KEY", "")
        ),
    ).execute()
    if not credential:
        logger.warning("evaluation.generation.skipped", extra={"reason": "no_llm_credential"})
        return None
    return HttpChatCompletionsLLM(
        api_url=os.getenv("LLM_API_URL", DEFAULT_LLM_API_URL),
        model=_llm_model(),
        api_key=credential,
    )


def _llm_model() -> str:
    return os.getenv("LLM_MODEL", "").strip() or DEFAULT_LLM_MODEL


def _parameters(
    args: argparse.Namespace,
    embedding_gateway: EmbeddingGateway,
    llm_gateway: LLMGateway | None,
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
        "context_top_k": str(args.context_top_k),
        "llm_model": _llm_model() if llm_gateway else "nao utilizado",
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
