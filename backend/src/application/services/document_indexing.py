from __future__ import annotations

from hashlib import sha256

from src.domain import (
    ExtractedDocument,
    AssistantId,
    DocumentChunker,
    DocumentExtractor,
    DocumentId,
    TransientServiceError,
    EmbeddingGateway,
    SparseEmbeddingGateway,
    SparseEncodingParameters,
    VectorChunk,
    article_from_section_path,
)

# Muda sempre que extracao, chunking ou metadados dos chunks mudarem de forma
# que exija reindexar (RF-32).
# "3": chunks passam a levar o vetor esparso da busca hibrida (SPEC-003).
# "4": estrutura de documentos normativos, campo ``legal_article`` e nova
# tokenizacao do BM25 (SPEC-012).
PIPELINE_VERSION = "4"


def hash_content(raw_content: bytes) -> str:
    return sha256(raw_content).hexdigest()


class DocumentIndexer:
    """Extrai, fragmenta e vetoriza um arquivo; usado na ingestao e na reindexacao."""

    def __init__(
        self,
        *,
        extractor: DocumentExtractor,
        chunker: DocumentChunker,
        embedding_gateway: EmbeddingGateway,
        sparse_embedding_gateway: SparseEmbeddingGateway,
    ) -> None:
        self._extractor = extractor
        self._chunker = chunker
        self._embedding_gateway = embedding_gateway
        self._sparse_embedding_gateway = sparse_embedding_gateway

    @property
    def embedding_model(self) -> str:
        return self._embedding_gateway.model_name

    @property
    def embedding_dimension(self) -> int:
        return self._embedding_gateway.dimension

    @property
    def sparse_parameters(self) -> SparseEncodingParameters | None:
        """Parametros do BM25 vigentes; ``None`` se o adaptador nao os expoe."""
        parameters = getattr(self._sparse_embedding_gateway, "parameters", None)
        return parameters if isinstance(parameters, SparseEncodingParameters) else None

    def supports(self, *, source_name: str, content_type: str | None) -> bool:
        return self._extractor.supports(
            filename=source_name,
            content_type=content_type,
        )

    def extract(
        self, *, source_name: str, content_type: str | None, raw_content: bytes
    ) -> ExtractedDocument:
        """SPEC-018: o texto estruturado, para contar tokens e dividir em secoes."""
        return self._extractor.extract(
            filename=source_name,
            content_type=content_type,
            raw_content=raw_content,
        )

    def build_chunks(
        self,
        *,
        assistant_id: AssistantId,
        document_id: DocumentId,
        source_name: str,
        content_type: str | None,
        raw_content: bytes,
        allowed_groups: frozenset[str] = frozenset(),
        active: bool = True,
        extracted: ExtractedDocument | None = None,
        owner_user_id: str | None = None,
        conversation_id: str | None = None,
    ) -> list[VectorChunk]:
        """``allowed_groups`` e a restricao vigente do documento (RF-43).

        ``active=False`` grava os trechos fora das buscas, para que o documento
        so passe a responder quando estiver indexado (RN-27, RN-28).

        SPEC-018: ``extracted`` evita extrair de novo; ``owner_user_id`` e
        ``conversation_id`` marcam os trechos do documento pessoal (RN-59).
        """
        if extracted is None:
            extracted = self.extract(
                source_name=source_name,
                content_type=content_type,
                raw_content=raw_content,
            )
        chunks = self._chunker.chunk(extracted)
        texts = [chunk.text for chunk in chunks]
        vectors = self._embedding_gateway.embed_documents(texts)
        sparse_vectors = self._sparse_embedding_gateway.embed_documents(texts)
        if len(vectors) != len(chunks) or len(sparse_vectors) != len(chunks):
            # Falha do provedor, nao do documento: vale nova tentativa.
            raise TransientServiceError(
                "embedding provider returned an unexpected vector count."
            )
        content_hash = hash_content(raw_content)
        groups = tuple(sorted(allowed_groups))
        return [
            VectorChunk(
                id=f"{document_id.value}:{chunk.index}",
                document_id=document_id,
                assistant_id=assistant_id,
                chunk_index=chunk.index,
                source_name=source_name,
                content_hash=content_hash,
                text=chunk.text,
                vector=vector,
                section_path=chunk.section_label,
                page=chunk.page,
                embedding_model=self.embedding_model,
                pipeline_version=PIPELINE_VERSION,
                sparse_vector=sparse_vector,
                allowed_groups=groups,
                active=active,
                legal_article=article_from_section_path(chunk.section_path),
                owner_user_id=owner_user_id,
                conversation_id=conversation_id,
            )
            for chunk, vector, sparse_vector in zip(chunks, vectors, sparse_vectors)
        ]
