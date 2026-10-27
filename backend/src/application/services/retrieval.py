from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from src.domain import (
    AssistantId,
    CollectionName,
    EmbeddingGateway,
    LegalReference,
    RerankerGateway,
    SearchResult,
    SparseEmbeddingGateway,
    VectorStoreGateway,
    mentions_part,
    parse_legal_reference,
)

# Teto de trechos lidos por artigo. O maior artigo esperado (o 5º da
# Constituicao) tem algumas dezenas de trechos, mas o mesmo numero pode existir
# em varias normas do assistente: o teto fica bem acima disso, porque a ordem
# so e feita depois da leitura (revisao B3). Atingi-lo fica registrado no log.
ARTICLE_MAX_CHUNKS = 2000
# D7: palavras da pergunta comparadas ao nome do documento.
_NAME_WORD = re.compile(r"[a-z0-9]{4,}")
logger = logging.getLogger(__name__)

_REFERENCE_WORDS = frozenset(
    {"artigo", "artigos", "inciso", "incisos", "paragrafo", "unico", "alinea"}
)


@dataclass(frozen=True, slots=True)
class RetrievalSettings:
    """Parametros da SPEC-003; os valores iniciais serao calibrados no CT-22."""

    candidates: int = 30
    top_n: int = 5
    min_score: float = 0.5
    context_token_budget: int = 2000
    history_token_budget: int = 1500
    # SPEC-012 (D8): orcamento quando o contexto e um artigo inteiro.
    structural_context_token_budget: int = 16000

    def __post_init__(self) -> None:
        if self.candidates < 1 or self.top_n < 1:
            raise ValueError("candidates and top_n must be positive.")
        if not 0.0 <= self.min_score <= 1.0:
            raise ValueError("min_score must be between 0 and 1.")
        if self.context_token_budget < 1:
            raise ValueError("context_token_budget must be positive.")
        if self.history_token_budget < 0:
            raise ValueError("history_token_budget must not be negative.")
        if self.structural_context_token_budget < 1:
            raise ValueError("structural_context_token_budget must be positive.")


@dataclass(frozen=True, slots=True)
class StructuralContext:
    """Contexto de um dispositivo citado na pergunta (SPEC-012, D6)."""

    reference: LegalReference
    results: list[SearchResult]

    @property
    def documents(self) -> int:
        return len({item.document_id.value for item in self.results})


class ContextRetriever:
    """Busca hibrida, reranking e nota minima; usado pelo chat e pela avaliacao."""

    def __init__(
        self,
        *,
        embedding_gateway: EmbeddingGateway,
        sparse_embedding_gateway: SparseEmbeddingGateway,
        vector_store_gateway: VectorStoreGateway,
        reranker_gateway: RerankerGateway,
        settings: RetrievalSettings,
    ) -> None:
        self._embedding_gateway = embedding_gateway
        self._sparse_embedding_gateway = sparse_embedding_gateway
        self._vector_store_gateway = vector_store_gateway
        self._reranker_gateway = reranker_gateway
        self._settings = settings

    @property
    def settings(self) -> RetrievalSettings:
        return self._settings

    def search(
        self,
        assistant_id: AssistantId,
        query: str,
        payload_filter: dict[str, str] | None = None,
        *,
        user_groups: frozenset[str] | None,
    ) -> list[SearchResult]:
        """Candidatos da busca hibrida, restritos a collection do assistente.

        ``user_groups`` e obrigatorio: sao os grupos de quem pergunta, usados
        pelo vector store para deixar de fora documentos restritos (RF-43).
        ``None`` so cabe a processos sem usuario, como a avaliacao.
        """
        dense_vector = self._embedding_gateway.embed_query(query)
        if not dense_vector:
            return []
        results = self._vector_store_gateway.hybrid_search(
            collection_name=CollectionName.from_assistant_id(assistant_id),
            dense_vector=dense_vector,
            sparse_vector=self._sparse_embedding_gateway.embed_query(query),
            limit=self._settings.candidates,
            payload_filter=payload_filter,
            user_groups=user_groups,
        )
        return [item for item in results if item.text.strip()]

    def rerank(
        self,
        query: str,
        candidates: list[SearchResult],
        limit: int | None = None,
    ) -> list[SearchResult]:
        """Os ``limit`` melhores candidatos (padrao ``top_n``), ja com a nota."""
        if not candidates:
            return []
        ranked = sorted(
            self._reranker_gateway.rerank(query, candidates),
            key=lambda item: item.score,
            reverse=True,
        )
        return ranked[: max(limit or self._settings.top_n, 1)]

    def structural_context(
        self,
        assistant_id: AssistantId,
        query: str,
        candidates: list[SearchResult],
        *,
        user_groups: frozenset[str] | None,
    ) -> StructuralContext | None:
        """D6: a pergunta cita um artigo e a base tem trechos marcados com ele.

        Os trechos vem da leitura de artigo, com os mesmos filtros de acesso e
        de trecho ativo da busca (RN-34); ``candidates`` (busca hibrida da
        mesma pergunta) so ajuda a escolher o documento (D7). ``None`` quando
        nao ha referencia ou nenhum trecho legivel: vale a busca hibrida.
        """
        reference = parse_legal_reference(query)
        if reference is None:
            return None
        fetched = self._vector_store_gateway.fetch_article(
            CollectionName.from_assistant_id(assistant_id),
            reference.article,
            ARTICLE_MAX_CHUNKS,
            user_groups=user_groups,
        )
        if len(fetched) >= ARTICLE_MAX_CHUNKS:
            logger.warning(
                "retrieval.article.truncated",
                extra={"article": reference.article, "limit": ARTICLE_MAX_CHUNKS},
            )
        runs = _article_runs([item for item in fetched if item.text.strip()])
        if not runs:
            return None
        chosen = _choose_runs(runs, candidates, query)
        if reference.targets_part:
            results = [
                item for run in chosen for item in self._part_of(query, reference, run)
            ]
        else:
            results = [item for run in chosen for item in run]
        return StructuralContext(reference=reference, results=results)

    def _part_of(
        self,
        query: str,
        reference: LegalReference,
        run: list[SearchResult],
    ) -> list[SearchResult]:
        """Caput e o inciso ou paragrafo pedido; sem o marcador, o reranker escolhe."""
        caput, rest = run[0], run[1:]
        found = [item for item in rest if mentions_part(item.text, reference)]
        if not found and rest:
            chosen_ids = {item.chunk_id for item in self.rerank(query, rest)}
            found = [item for item in rest if item.chunk_id in chosen_ids]
        return [caput, *found]

    def select_relevant(self, ranked: list[SearchResult]) -> list[SearchResult]:
        """RN-17: so trechos com nota igual ou superior a minima viram contexto."""
        return [
            item
            for item in ranked[: self._settings.top_n]
            if item.score >= self._settings.min_score
        ]


def _article_runs(results: list[SearchResult]) -> list[list[SearchResult]]:
    """Trechos consecutivos do mesmo documento formam um artigo.

    Um documento pode ter dois artigos com o mesmo numero (por exemplo, as
    disposicoes transitorias de uma lei): a quebra no ``chunk_index`` os separa.
    """
    ordered = sorted(
        results, key=lambda item: (item.document_id.value, item.chunk_index or 0)
    )
    runs: list[list[SearchResult]] = []
    for item in ordered:
        last = runs[-1][-1] if runs else None
        if (
            last is not None
            and last.document_id == item.document_id
            and item.chunk_index is not None
            and last.chunk_index is not None
            and item.chunk_index == last.chunk_index + 1
        ):
            runs[-1].append(item)
        else:
            runs.append([item])
    return runs


def _choose_runs(
    runs: list[list[SearchResult]],
    candidates: list[SearchResult],
    query: str,
) -> list[list[SearchResult]]:
    """D7: o artigo que a busca hibrida achou primeiro; senao, o nome do documento.

    Empate: o primeiro artigo de cada documento empatado, pela ordem do nome.
    """
    positions = {item.chunk_id: index for index, item in enumerate(candidates)}
    hinted = [
        (min(positions[item.chunk_id] for item in run if item.chunk_id in positions), run)
        for run in runs
        if any(item.chunk_id in positions for item in run)
    ]
    if hinted:
        return [min(hinted, key=lambda pair: pair[0])[1]]
    first_by_document: dict[str, list[SearchResult]] = {}
    for run in runs:
        first_by_document.setdefault(run[0].document_id.value, run)
    words = set(_NAME_WORD.findall(_fold(query))) - _REFERENCE_WORDS
    overlap = {
        document: sum(word in _fold(run[0].source_name) for word in words)
        for document, run in first_by_document.items()
    }
    best = max(overlap.values())
    tied = [run for document, run in first_by_document.items() if overlap[document] == best]
    return sorted(tied, key=lambda run: (run[0].source_name, run[0].document_id.value))


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))
