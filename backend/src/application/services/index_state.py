from __future__ import annotations

from dataclasses import dataclass

from src.domain import (
    AssistantId,
    CollectionName,
    Document,
    VectorStoreGateway,
)

_FIRST_VERSION = 1
# A collection do MVP nao tem sufixo e conta como a versao 1.
_VERSION_AFTER_LEGACY = 2


@dataclass(frozen=True, slots=True)
class IndexState:
    """Situacao das collections de um assistente.

    ``current`` e a collection versionada para a qual o alias aponta.
    ``legacy`` indica a collection do MVP, que ocupa o nome do alias e guarda
    vetores incompativeis com o modelo semantico.
    """

    assistant_id: AssistantId
    alias: CollectionName
    current: CollectionName | None
    legacy: bool

    def next_collection(self) -> CollectionName:
        if self.current is not None:
            version = (self.current.version or _FIRST_VERSION) + 1
        elif self.legacy:
            version = _VERSION_AFTER_LEGACY
        else:
            version = _FIRST_VERSION
        return CollectionName.versioned(self.assistant_id, version)


def read_index_state(
    vector_store_gateway: VectorStoreGateway,
    assistant_id: AssistantId,
) -> IndexState:
    alias = CollectionName.from_assistant_id(assistant_id)
    current = vector_store_gateway.resolve_alias(alias)
    legacy = current is None and vector_store_gateway.collection_exists(alias)
    return IndexState(
        assistant_id=assistant_id,
        alias=alias,
        current=current,
        legacy=legacy,
    )


def is_index_outdated(
    state: IndexState,
    documents: list[Document],
    *,
    embedding_model: str,
    pipeline_version: str,
) -> bool:
    """RN-16: base gerada por outro modelo ou pipeline exige reindexacao."""
    if state.legacy:
        return True
    return any(
        document.is_indexed
        and not document.is_current(
            embedding_model=embedding_model,
            pipeline_version=pipeline_version,
        )
        for document in documents
    )
