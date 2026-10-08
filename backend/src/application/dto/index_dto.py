from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain import ReindexJob


@dataclass(frozen=True, slots=True)
class ReindexJobDTO:
    id: str
    assistant_id: str
    status: str
    target_collection: str
    total_documents: int
    processed_documents: int
    error: str | None
    started_at: datetime
    finished_at: datetime | None

    @classmethod
    def from_entity(cls, job: ReindexJob) -> "ReindexJobDTO":
        return cls(
            id=job.id,
            assistant_id=job.assistant_id.value,
            status=job.status.value,
            target_collection=job.target_collection,
            total_documents=job.total_documents,
            processed_documents=job.processed_documents,
            error=job.error,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


@dataclass(frozen=True, slots=True)
class IndexStatusDTO:
    assistant_id: str
    embedding_model: str
    pipeline_version: str
    collection_name: str | None
    outdated: bool
    documents_total: int
    documents_indexed: int
    documents_without_original: tuple[str, ...]
    last_reindex: ReindexJobDTO | None
    # PC-D2: parametros do BM25 da collection vigente diferentes dos do
    # ambiente. So aviso; a correcao e reindexar.
    sparse_parameters_changed: bool = False
    sparse_parameters_recorded: dict[str, float] | None = None
    sparse_parameters_current: dict[str, float] | None = None
