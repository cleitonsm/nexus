from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from collections.abc import Iterator
from typing import Protocol

from .access import AuthenticatedUser
from .audit import AuditEvent, AuditQuery
from .chunking import DocumentChunk, ExtractedDocument
from .citations import ContextChunk
from .errors import DomainValidationError
from .feedback import FeedbackQuery, MessageFeedback
from .usage import (
    LLMCompletion,
    LLMStreamChunk,
    UsageLimitDecision,
    UsageLimits,
    UsageQuery,
    UsageRecord,
    UsageSummary,
)
from .entities import (
    Assistant,
    ChatMessage,
    Conversation,
    Document,
    IngestionJob,
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
    ) -> list[Document]:
        """Documentos vigentes; versoes substituidas ficam de fora (D5)."""
        ...

    def find_by_hash(
        self,
        assistant_id: AssistantId,
        content_hash: str,
    ) -> Document | None:
        """Documento vigente do assistente com o mesmo conteudo (RN-26)."""
        ...

    def delete(self, document_id: DocumentId) -> bool: ...


class IngestionJobQueue(Protocol):
    """Fila de processamento de documentos consumida pelo worker (RF-48)."""

    def enqueue(self, job: IngestionJob) -> IngestionJob: ...

    def reserve_next(self, now: datetime) -> IngestionJob | None:
        """Reserva o proximo job disponivel, sem disputa entre workers.

        Jobs de assistentes com reindexacao em curso nao sao reservados (D8).
        """
        ...

    def list_expired(self, reserved_before: datetime) -> list[IngestionJob]:
        """Jobs em processamento reservados antes do instante informado."""
        ...

    def complete(
        self,
        job: IngestionJob,
        document: Document,
        replaced: Document | None = None,
    ) -> None:
        """Conclui o job e grava o documento (e a versao substituida) juntos."""
        ...

    def retry(self, job: IngestionJob, document: Document) -> None:
        """Devolve o job a fila e o documento a pendente, na mesma transacao."""
        ...

    def fail(self, job: IngestionJob, document: Document) -> None:
        """Encerra o job com falha e grava o documento falho juntos."""
        ...


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

    def get_message(self, message_id: str) -> ChatMessage | None:
        """Mensagem pelo id, de qualquer conversa; quem chama confere o dono."""
        ...


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
    """Gera vetores esparsos localmente (RNF-26); o IDF fica com o indice.

    Adaptadores que dependem de parametros (BM25) os expoem em
    ``parameters`` (``SparseEncodingParameters``), para que a mudanca deles
    seja detectada (PC-D2).
    """

    def embed_documents(self, texts: list[str]) -> list[SparseVector]: ...

    def embed_query(self, text: str) -> SparseVector: ...


_PARAMETER_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class SparseEncodingParameters:
    """Parametros do BM25 com que os vetores esparsos foram gerados (PC-D2).

    Os vetores gravados nao mudam quando o ambiente muda: comparar o que foi
    usado na collection com o vigente revela a necessidade de reindexar.
    """

    k1: float
    b: float
    average_length: float

    def __post_init__(self) -> None:
        if self.k1 < 0 or not 0.0 <= self.b <= 1.0 or self.average_length <= 0:
            raise DomainValidationError("invalid sparse encoding parameters.")

    def matches(self, other: "SparseEncodingParameters") -> bool:
        return (
            abs(self.k1 - other.k1) <= _PARAMETER_TOLERANCE
            and abs(self.b - other.b) <= _PARAMETER_TOLERANCE
            and abs(self.average_length - other.average_length)
            <= _PARAMETER_TOLERANCE
        )

    def as_dict(self) -> dict[str, float]:
        return {"k1": self.k1, "b": self.b, "average_length": self.average_length}


class IndexParametersRepository(Protocol):
    """Parametros de codificacao registrados por collection (PC-D2)."""

    def get_sparse_parameters(
        self, collection_name: CollectionName
    ) -> SparseEncodingParameters | None: ...

    def save_sparse_parameters(
        self,
        collection_name: CollectionName,
        parameters: SparseEncodingParameters,
    ) -> None: ...


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
    # Trecho fora das buscas ate o documento terminar de ser indexado
    # (RN-27, RN-28).
    active: bool = True


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
        payload. Trechos inativos (documento ainda em processamento) nunca
        voltam (RN-27). Collection inexistente devolve lista vazia. Collection
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

    def delete_by_document(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
    ) -> None:
        """Remove todos os trechos do documento; collection inexistente nao e erro."""
        ...

    def set_document_active(
        self,
        collection_name: CollectionName,
        document_id: DocumentId,
        active: bool,
    ) -> None:
        """Inclui ou retira das buscas os trechos do documento (RN-28)."""
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

    def supports(self, *, filename: str | None, content_type: str | None) -> bool:
        """Indica, sem ler o conteudo, se o formato e aceito."""
        ...

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

    def delete(self, storage_key: str) -> None:
        """Remove o arquivo; chave sem arquivo nao e erro (RN-29)."""
        ...


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

    def generate_with_usage(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> LLMCompletion:
        """Como ``generate``, com o consumo de tokens (RF-57).

        ``system_instruction`` vai nas instrucoes de sistema, separada dos
        trechos recuperados, que nunca chegam la (RN-31).
        """
        ...

    def generate_stream(
        self,
        *,
        prompt: str,
        context_chunks: list[ContextChunk],
        conversation_history: list[ChatMessage],
        system_instruction: str | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Resposta em partes (RF-58); o consumo vem na ultima, se houver."""
        ...


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


class UsageRecordRepository(Protocol):
    """Perguntas feitas ao chat, com tokens e custo estimado (RF-57)."""

    def append(self, record: UsageRecord) -> UsageRecord: ...

    def summarize_by_user(self, query: UsageQuery) -> list[UsageSummary]: ...

    def summarize_by_conversation(self, query: UsageQuery) -> list[UsageSummary]: ...


class UsageLimiter(Protocol):
    """RN-32: decide se o usuario ainda pode perguntar na janela atual."""

    def check(
        self,
        user_id: str,
        limits: UsageLimits,
        now: datetime,
    ) -> UsageLimitDecision: ...


class UsageSettingsRepository(Protocol):
    """Limites definidos na tela; sem valor gravado, vale o do ambiente."""

    def get_limits(self) -> UsageLimits | None: ...

    def save_limits(self, limits: UsageLimits, *, updated_by: str) -> UsageLimits: ...


class FeedbackRepository(Protocol):
    def save(self, feedback: MessageFeedback) -> MessageFeedback: ...

    def get_by_id(self, feedback_id: str) -> MessageFeedback | None: ...

    def get_by_message(
        self,
        message_id: str,
        user_id: str,
    ) -> MessageFeedback | None: ...

    def list_feedback(self, query: FeedbackQuery) -> list[MessageFeedback]:
        """Da mais recente para a mais antiga."""
        ...
