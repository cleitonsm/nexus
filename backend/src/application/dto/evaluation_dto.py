from __future__ import annotations

from dataclasses import asdict, dataclass

from src.domain import EvaluationReport


@dataclass(frozen=True, slots=True)
class EvaluationReportDTO:
    assistant_id: str
    created_at: str
    k: int
    validated: bool
    metrics: dict[str, float | None]
    parameters: dict[str, str]
    items: list[dict[str, object]]

    @classmethod
    def from_report(cls, report: EvaluationReport) -> "EvaluationReportDTO":
        return cls(
            assistant_id=report.assistant_id.value,
            created_at=report.created_at.isoformat(),
            k=report.k,
            validated=report.validated,
            metrics=asdict(report.metrics),
            parameters=dict(report.parameters),
            items=[
                {**asdict(result), "retrieved_sources": list(result.retrieved_sources)}
                for result in report.item_results
            ],
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EvaluationComparisonDTO:
    deltas: dict[str, float]
    regressions: tuple[str, ...]
    tolerance: float

    @property
    def has_regression(self) -> bool:
        return bool(self.regressions)
