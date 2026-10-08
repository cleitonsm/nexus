from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .access import AuthenticatedUser
from .audit import AuditEvent, AuditQuery
from .chunking import DocumentChunk, ExtractedDocument
from .citations import ContextChunk
from .errors import DomainValidationError
from .entities import (
    Assistant,
    ChatMessage,
    Conversation,
    Document,
    ReindexJob,
)
from .value_objects import (
    AssistantId,
    CollectionName,
    ConversationId,
    DocumentId,
)


class AssistantRepository(Protocol):
    def save(self, assistant: Assistant) -> Assistant: ...

    def list_all(self) -> list[Assistant]: ...

    def get_by_id(self, assistant_id: AssistantId) -> Assistant | None: ...

    def delete(self, assistant_id: AssistantId) -> bool: ...


class DocumentRepository(Protocol):
    def save(self, document: Document) -> Document: ...

    def get_by_id(self, document_id: DocumentId) -> Document | None: ...

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
    ) -> list[Document]: ...

    def delete(self, document_id: DocumentId) -> bool: ...


class ReindexJobRepository(Protocol):
    def save(self, job: ReindexJob) -> ReindexJob: ...

    def get_by_id(self, job_id: str) -> ReindexJob | None: ...

    def get_latest(self, assistant_id: AssistantId) -> ReindexJob | None: ...

    def get_running(self, assistant_id: AssistantId) -> ReindexJob | None: ...

    def list_running(self) -> list[ReindexJob]: ...


class ConversationRepository(Protocol):
    def save(self, conversation: Conversation) -> Conversation: ...

    def get_by_id(
        self,
        conversation_id: ConversationId,
    ) -> Conversation | None: ...

    def list_by_assistant(
        self,
        assistant_id: AssistantId,
        owner_user_id: str,
    ) -> list[Conversation]:
        """Conversas do assistente que pertencem ao usuario (RN-24)."""
        ...

    def save_message(self, message: ChatMessage) -> ChatMessage: ...

    def list_messages(
        self,
        conversation_id: ConversationId,
    ) -> list[ChatMessage]: ...

    def delete(self, conversation_id: ConversationId) -> bool: ...


class SecretSettingsRepository(Protocol):
    def set_encrypted_value(
        self,
        *,
        key_name: str,
        encrypted_value: str,
    ) -> None: ...

    def get_encrypted_value(self, *, key_name: str) -> str | None: ...


class EmbeddingGateway(Protocol):
    """Vetoriza localmente; documentos e consultas tem entradas distintas."""

    @property
    def model_name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


@dataclass(frozen=True, slots=True)
class SparseVector:
    """Vetor esparso: pesos de termos em posicoes de um vocabulario aberto."""

    indices: tuple[int, ...] = ()
    values: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if len(self.indices) != len(self.values):
            raise DomainValidationError(
                "sparse vector indices and values must have the same length."
            )
        if len(set(self.indices)) != len(self.indices):
            raise DomainValidationError("sparse vector indices must be unique.")

    @property
    def is_empty(self) -> bool:
        return not self.indices


class SparseEmbeddingGateway(Protocol):
    """Gera vetores esparsos localmente (RNF-26); o IDF fica com o indice."""

    def embed_documents(self, texts: list[str]) -> list[SparseVector]: ...

    def embed_query(self, text: str) -> SparseVector: ...


@dataclass(frozen=True, slots=True)
class VectorChunk:
    id: str
    document_id: DocumentId
    assistant_id: AssistantId
    chunk_index: int
    source_name: str
    content_hash: str
    text: str
    vector: list[float]
    section_path: str = ""
    page: int | None = None
    embedding_model: str = ""
    pipeline_version: str = ""
    sparse_vector: SparseVector | None = None
    # Grupos a que o documento esta restrito; vazio segue o assistente (RF-43).
    allowed_groups: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Trecho recuperado; ``score`` e a nota da etapa que o produziu."""

    chunk_id: str
    document_id: DocumentId
    score: float
    text: str
    source_name: str = ""
    section_path: str = ""
    page: int | None = None


class VectorStoreGateway(Protocol):
    def ensure_collection(
        self,
        collection_name: CollectionName,
        vector_size: int,
    ) -> None: ...

    def upsert_chunks(
        self,
        collection_name: CollectionName,
        chunks: list[VectorChunk],
    ) -> None: ...

    def hybrid_search(
        self,
        collection_name: CollectionName,
        dense_vector: list[float],
        sparse_vector: SparseVector,
        limit: int,
        payload_filter: dict[str, str] | None = None,
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        """Busca densa e esparsa com fusao RRF (RF-33).

        ``user_groups`` e obrigatorio e aplica, dentro da consulta, a restricao
        por documento (RF-43, RNF-23): so voltam trechos sem restricao ou
        restritos a algum desses grupos. ``None`` desliga a restricao e e
        reservado a processos sem usuario, como a avaliacao.

        ``payload_filter`` restringe os candidatos por igualdade de campos do
        payload. Collection inexistente devolve lista vazia. Collection
        anterior a busca hibrida e consultada so pelo vetor denso; se nem isso
        for possivel, levanta ``IndexOutdatedError``.
        """
        ...

    def set_document_groups(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None:
        """Regrava a restricao nos trechos do documento, sem reindexar vetores.

        Collection inexistente nao e erro: o documento ainda nao tem trechos.
        """
        ...

    def delete_collection(self, collection_name: CollectionName) -> None: ...

    def collection_exists(self, collection_name: CollectionName) -> bool:
        """Indica se existe uma collection fisica com esse nome (nao um alias)."""
        ...

    def count_points(self, collection_name: CollectionName) -> int: ...

    def resolve_alias(self, alias: CollectionName) -> CollectionName | None:
        """Collection para a qual o alias aponta, ou None se nao existir."""
        ...

    def point_alias(
        self,
        alias: CollectionName,
        collection_name: CollectionName,
    ) -> None:
        """Cria o alias ou o troca de forma atomica."""
        ...


class TokenCounter(Protocol):
    """Mede textos com o tokenizador do modelo de embedding."""

    @property
    def max_tokens(self) -> int:
        """Limite de sequencia do modelo, incluidos os tokens especiais."""
        ...

    def count(self, text: str) -> int:
        """Tokens que o modelo consome para o texto, incluidos os especiais."""
        ...


class DocumentChunker(Protocol):
    def chunk(self, document: ExtractedDocument) -> list[DocumentChunk]: ...


class DocumentExtractor(Protocol):
    """Converte o arquivo enviado em blocos; ValueError para arquivo invalido."""

    def extract(
        self,
        *,
        filename: str | None,
        content_type: str | None,
        raw_content: bytes,
    ) -> ExtractedDocument: ...


class DocumentFileStorage(Protocol):
    """Guarda o arquivo original para reprocessamento."""

    def save(
        self,
        *,
        assistant_id: AssistantId,
        document_id: DocumentId,
        filename: str,
        content: bytes,
    ) -> str:
        """Grava o arquivo e devolve a chave de armazenamento."""
        ...

    def load(self, storage_key: str) -> bytes: ...


class RerankerGateway(Protocol):
    """Reordena candidatos localmente com uma nota de relevancia (RF-34)."""

    @property
    def model_name(self) -> str: ...

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
    ) -> list[SearchResult]:
        """Devolve os candidatos com ``score`` entre 0 e 1, do maior ao menor."""
        ...


class LLMGateway(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
    ) -> str: ...


class AnswerJudge(Protocol):
    """Julga se uma resposta e sustentada pelo contexto recuperado."""

    def is_faithful(
        self,
        *,
        question: str,
        answer: str,
        context_chunks: list[str],
    ) -> bool: ...


class TokenVerifier(Protocol):
    """Valida o token de acesso e devolve quem o apresentou (RNF-22)."""

    def verify(self, token: str) -> AuthenticatedUser:
        """Levanta ``AuthenticationError`` para qualquer token nao aceito."""
        ...


class AssistantPermissionRepository(Protocol):
    """Vinculos de assistentes e de documentos com grupos (RF-42, RF-43)."""

    def get_assistant_groups(self, assistant_id: AssistantId) -> frozenset[str]: ...

    def list_assistant_groups(self) -> dict[str, frozenset[str]]:
        """Grupos por id de assistente; assistentes sem grupo ficam de fora."""
        ...

    def set_assistant_groups(
        self,
        assistant_id: AssistantId,
        groups: frozenset[str],
    ) -> None: ...

    def get_document_groups(self, document_id: DocumentId) -> frozenset[str]: ...

    def list_document_groups(
        self,
        assistant_id: AssistantId,
    ) -> dict[str, frozenset[str]]:
        """Grupos por id de documento do assistente; sem restricao fica de fora."""
        ...

    def set_document_groups(
        self,
        document_id: DocumentId,
        groups: frozenset[str],
    ) -> None: ...


class AuditRetentionRepository(Protocol):
    """Remocao por retencao (RNF-24), separada da trilha usada pela aplicacao.

    So o comando de manutencao a recebe: nenhuma rota nem caso de uso de
    usuario consegue apagar eventos (RN-25).
    """

    def purge_older_than(self, cutoff: datetime) -> int:
        """Apaga os eventos anteriores a ``cutoff`` e devolve quantos eram."""
        ...


class AuditLogRepository(Protocol):
    """Trilha somente de inclusao: nao ha alteracao nem exclusao (RN-25)."""

    def append(self, event: AuditEvent) -> AuditEvent: ...

    def list_events(self, query: AuditQuery) -> list[AuditEvent]:
        """Eventos do mais recente para o mais antigo."""
        ...
