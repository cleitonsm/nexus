"""Calibracao da nota minima de relevancia (CT-22), sem chamar o LLM."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.services import ContextRetriever
from src.domain import AssistantId, DocumentRepository, EvaluationItem

DEFAULT_THRESHOLDS: tuple[float, ...] = tuple(
    round(step / 20, 2) for step in range(1, 20)
)


@dataclass(frozen=True, slots=True)
class CalibrateRelevanceInput:
    assistant_id: str
    items: tuple[EvaluationItem, ...]
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS


@dataclass(frozen=True, slots=True)
class ItemScores:
    item_id: str
    out_of_scope: bool
    # Maior nota entre os ``top_n`` trechos; ``None`` sem candidatos.
    top_score: float | None
    # Maior nota entre os trechos da fonte esperada (so dentro do escopo).
    source_score: float | None


@dataclass(frozen=True, slots=True)
class ThresholdPoint:
    threshold: float
    # Dentro do escopo: perguntas cuja fonte correta passa na nota minima.
    answered_in_scope: float | None
    # Fora do escopo: perguntas que acabam em fallback (nenhum trecho passa).
    refused_out_of_scope: float | None
    balanced: float | None


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    current_threshold: float
    items: tuple[ItemScores, ...]
    points: tuple[ThresholdPoint, ...]
    best: ThresholdPoint | None


class CalibrateRelevanceUseCase:
    """Varre a nota minima sobre as notas reais do reranker.

    So recuperacao e reranking: nenhuma chamada ao LLM. O resultado apoia a
    decisao, que continua sendo de uma pessoa.
    """

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        context_retriever: ContextRetriever,
    ) -> None:
        self._document_repository = document_repository
        self._retriever = context_retriever

    def execute(self, data: CalibrateRelevanceInput) -> CalibrationReport:
        if not data.items:
            raise ValueError("calibration requires at least one item.")
        if not data.thresholds:
            raise ValueError("calibration requires at least one threshold.")
        # Perguntas de continuacao dependem da reescrita pelo LLM; esta
        # ferramenta nao chama o LLM, entao elas ficam de fora da varredura.
        items = tuple(item for item in data.items if not item.history)
        if not items:
            raise ValueError("calibration requires at least one item without history.")
        assistant_id = AssistantId(data.assistant_id)
        names = {
            doc.id.value: doc.source_name
            for doc in self._document_repository.list_by_assistant(assistant_id)
        }
        scores = tuple(
            self._scores(item, assistant_id, names) for item in items
        )
        points = tuple(
            _point(threshold, scores) for threshold in sorted(data.thresholds)
        )
        return CalibrationReport(
            current_threshold=self._retriever.settings.min_score,
            items=scores,
            points=points,
            best=_best(points),
        )

    def _scores(
        self,
        item: EvaluationItem,
        assistant_id: AssistantId,
        names: dict[str, str],
    ) -> ItemScores:
        candidates = self._retriever.search(
            assistant_id, item.question, user_groups=None
        )
        ranked = self._retriever.rerank(item.question, candidates)
        top_n = ranked[: self._retriever.settings.top_n]
        expected = {name.strip() for name in item.source_documents}
        source = [
            hit.score
            for hit in top_n
            if names.get(hit.document_id.value, "") in expected
        ]
        return ItemScores(
            item_id=item.id,
            out_of_scope=item.out_of_scope,
            top_score=max((hit.score for hit in top_n), default=None),
            source_score=None if item.out_of_scope else max(source, default=None),
        )


def _point(threshold: float, scores: tuple[ItemScores, ...]) -> ThresholdPoint:
    inside = [s for s in scores if not s.out_of_scope]
    outside = [s for s in scores if s.out_of_scope]
    answered = _ratio(
        [s.source_score is not None and s.source_score >= threshold for s in inside]
    )
    refused = _ratio(
        [s.top_score is None or s.top_score < threshold for s in outside]
    )
    parts = [value for value in (answered, refused) if value is not None]
    return ThresholdPoint(
        threshold=threshold,
        answered_in_scope=answered,
        refused_out_of_scope=refused,
        balanced=sum(parts) / len(parts) if parts else None,
    )


def _best(points: tuple[ThresholdPoint, ...]) -> ThresholdPoint | None:
    """Maior media entre acerto e recusa; no empate, a nota mais baixa."""
    scored = [point for point in points if point.balanced is not None]
    if not scored:
        return None
    return max(scored, key=lambda point: (point.balanced, -point.threshold))


def _ratio(flags: list[bool]) -> float | None:
    return sum(flags) / len(flags) if flags else None
