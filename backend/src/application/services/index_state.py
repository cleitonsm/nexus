from __future__ import annotations

from dataclasses import dataclass

from src.domain import (
    AssistantId,
    CollectionName,
    Document,
    IndexParametersRepository,
    SparseEncodingParameters,
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


@dataclass(frozen=True, slots=True)
class SparseParametersCheck:
    """Parametros do BM25 da collection vigente comparados aos do ambiente.

    ``recorded`` vazio (collection sem registro ou sem repositorio) nao conta
    como mudanca. PC-D2: a divergencia so avisa; nada e bloqueado.
    """

    recorded: SparseEncodingParameters | None
    current: SparseEncodingParameters | None

    @property
    def changed(self) -> bool:
        if self.recorded is None or self.current is None:
            return False
        return not self.recorded.matches(self.current)


def check_sparse_parameters(
    state: IndexState,
    repository: IndexParametersRepository | None,
    current: SparseEncodingParameters | None,
) -> SparseParametersCheck:
    if repository is None or state.current is None:
        return SparseParametersCheck(recorded=None, current=current)
    return SparseParametersCheck(
        recorded=repository.get_sparse_parameters(state.current),
        current=current,
    )


def record_sparse_parameters(
    repository: IndexParametersRepository | None,
    collection_name: CollectionName,
    parameters: SparseEncodingParameters | None,
) -> None:
    """Registra os parametros com que a collection passa a ser gerada."""
    if repository is None or parameters is None:
        return
    repository.save_sparse_parameters(collection_name, parameters)
