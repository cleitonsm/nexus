"""Calibra a nota minima de relevancia (CT-22) com o conjunto de referencia.

Uso: python -m src.cli.calibrate_relevance --dataset <arquivo.jsonl>

Usa a base do assistente piloto ja indexada pelo comando de avaliacao e nao
chama o LLM. O comando so mostra os numeros: o valor de RELEVANCE_MIN_SCORE
continua sendo uma decisao de quem opera o sistema.

SPEC-013 (RF-95): com ``--assistant-name`` calibra qualquer assistente, com os
candidatos, o top_k e a busca hibrida dele; a nota atual mostrada e a dele.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from src.application.services import ContextRetriever, assistant_retrieval_settings
from src.application.use_cases import (
    DEFAULT_THRESHOLDS,
    CalibrateRelevanceInput,
    CalibrateRelevanceUseCase,
)
from src.cli.calibration_report import format_report, to_dict
from src.infrastructure.composition import (
    build_embedding_gateway,
    build_reranker_gateway,
    build_sparse_embedding_gateway,
    retrieval_settings,
)
from src.infrastructure.database import (
    PostgresAssistantRepository,
    PostgresDocumentRepository,
    SessionLocal,
    run_migrations,
)
from src.infrastructure.evaluation import (
    EvaluationDatasetError,
    JsonlEvaluationDatasetLoader,
)
from src.infrastructure.observability import configure_logging
from src.infrastructure.vector_store import QdrantVectorStoreGateway

EXIT_OK = 0
EXIT_INVALID_DATASET = 2
EXIT_NO_ASSISTANT = 3


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    configure_logging(level=os.getenv("LOG_LEVEL", "WARNING"))
    try:
        items = JsonlEvaluationDatasetLoader(
            allow_unvalidated=args.allow_unvalidated
        ).load(args.dataset)
    except EvaluationDatasetError as exc:
        for problem in exc.errors:
            print(f"dataset invalido: {problem}", file=sys.stderr)
        return EXIT_INVALID_DATASET

    run_migrations()
    with SessionLocal() as session:
        assistant = next(
            (
                item
                for item in PostgresAssistantRepository(session=session).list_all()
                if item.name.value == args.assistant_name
            ),
            None,
        )
        if assistant is None:
            print(
                f'assistente "{args.assistant_name}" nao encontrado: rode '
                "scripts/eval.ps1 antes para indexar a base do piloto.",
                file=sys.stderr,
            )
            return EXIT_NO_ASSISTANT
        report = CalibrateRelevanceUseCase(
            document_repository=PostgresDocumentRepository(session=session),
            context_retriever=ContextRetriever(
                embedding_gateway=build_embedding_gateway(),
                sparse_embedding_gateway=build_sparse_embedding_gateway(),
                vector_store_gateway=QdrantVectorStoreGateway(
                    url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
                    api_key=os.getenv("QDRANT_API_KEY", "") or None,
                ),
                reranker_gateway=build_reranker_gateway(),
                settings=assistant_retrieval_settings(assistant, retrieval_settings()),
            ),
        ).execute(
            CalibrateRelevanceInput(
                assistant_id=assistant.id.value,
                items=tuple(items),
                thresholds=args.thresholds,
            )
        )
    print(format_report(report))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(to_dict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return EXIT_OK


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Varre a nota minima de relevancia sobre o conjunto de referencia."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--assistant-name", default="Nexus Docs (avaliacao)")
    parser.add_argument("--allow-unvalidated", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--thresholds",
        type=lambda text: tuple(float(part) for part in text.split(",")),
        default=DEFAULT_THRESHOLDS,
        help="notas separadas por virgula (padrao: 0,05 a 0,95 de 0,05 em 0,05)",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    sys.exit(main())
