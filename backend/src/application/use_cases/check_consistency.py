"""Conferencia de contagens entre PostgreSQL e Qdrant (R18, decisao PC-D3).

Comando sob demanda (``python -m src.cli.check_consistency``). Compara, por
assistente, a quantidade de trechos que cada documento deveria ter na
collection vigente com a que o Qdrant guarda, e aponta trechos de documentos
que o PostgreSQL nao conhece. So le: nada e corrigido automaticamente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.application.services import read_index_state
from src.domain import (
    AssistantId,
    AssistantRepository,
    Document,
    DocumentRepository,
    DocumentStatus,
    ReindexJobRepository,
    VectorStoreGateway,
)

SKIPPED_LEGACY = "base do MVP; reindexe o assistente"
SKIPPED_REINDEXING = "reindexacao em curso"

# Pendentes e em processamento podem ter trechos parciais (inativos): ficam
# de fora da conferencia ate o worker terminar.
_IN_PROGRESS = (DocumentStatus.PENDING, DocumentStatus.PROCESSING)


@dataclass(frozen=True, slots=True)
class DocumentDivergence:
    document_id: str
    source_name: str
    status: str
    expected: int
    found: int


@dataclass(frozen=True, slots=True)
class AssistantConsistency:
    assistant_id: str
    collection_name: str | None
    documents_checked: int = 0
    divergences: tuple[DocumentDivergence, ...] = ()
    # Trechos de documentos ausentes do PostgreSQL: (document_id, pontos).
    orphan_documents: tuple[tuple[str, int], ...] = ()
    skipped_reason: str | None = None

    @property
    def consistent(self) -> bool:
        return not self.divergences and not self.orphan_documents


@dataclass(frozen=True, slots=True)
class ConsistencyReport:
    assistants: tuple[AssistantConsistency, ...] = field(default_factory=tuple)

    @property
    def consistent(self) -> bool:
        return all(item.consistent for item in self.assistants)

    @property
    def divergence_count(self) -> int:
        return sum(
            len(item.divergences) + len(item.orphan_documents)
            for item in self.assistants
        )


def expected_points(document: Document) -> int | None:
    """Trechos esperados na collection vigente; ``None`` fica de fora."""
    if document.status in _IN_PROGRESS:
        return None
    if document.status is DocumentStatus.INDEXED:
        return document.chunk_count
    # Falhou ou substituido: os trechos ja deveriam ter saido (RN-28, RN-29).
    return 0


class CheckIndexConsistencyUseCase:
    def __init__(
        self,
        *,
        assistant_repository: AssistantRepository,
        document_repository: DocumentRepository,
        vector_store_gateway: VectorStoreGateway,
        reindex_job_repository: ReindexJobRepository,
    ) -> None:
        self._assistants = assistant_repository
        self._documents = document_repository
        self._vector_store = vector_store_gateway
        self._reindex_jobs = reindex_job_repository

    def execute(self, assistant_id: str | None = None) -> ConsistencyReport:
        if assistant_id is not None:
            ids = [AssistantId(assistant_id)]
        else:
            ids = [assistant.id for assistant in self._assistants.list_all()]
        return ConsistencyReport(
            assistants=tuple(self._check(item) for item in ids)
        )

    def _check(self, assistant_id: AssistantId) -> AssistantConsistency:
        state = read_index_state(self._vector_store, assistant_id)
        collection = state.current
        name = collection.value if collection else None
        if state.legacy:
            return AssistantConsistency(
                assistant_id=assistant_id.value,
                collection_name=state.alias.value,
                skipped_reason=SKIPPED_LEGACY,
            )
        if self._reindex_jobs.get_running(assistant_id) is not None:
            return AssistantConsistency(
                assistant_id=assistant_id.value,
                collection_name=name,
                skipped_reason=SKIPPED_REINDEXING,
            )
        documents = self._documents.list_by_assistant(assistant_id)
        found = (
            self._vector_store.count_points_by_document(collection)
            if collection is not None
            else {}
        )
        divergences: list[DocumentDivergence] = []
        checked = 0
        for document in documents:
            expected = expected_points(document)
            if expected is None:
                continue
            checked += 1
            stored = found.get(document.id.value, 0)
            if stored != expected:
                divergences.append(
                    DocumentDivergence(
                        document_id=document.id.value,
                        source_name=document.source_name,
                        status=document.status.value,
                        expected=expected,
                        found=stored,
                    )
                )
        known = {document.id.value for document in documents}
        orphans = tuple(
            sorted(
                (document_id, count)
                for document_id, count in found.items()
                if document_id not in known
            )
        )
        return AssistantConsistency(
            assistant_id=assistant_id.value,
            collection_name=name,
            documents_checked=checked,
            divergences=tuple(divergences),
            orphan_documents=orphans,
        )
