from __future__ import annotations

from dataclasses import dataclass

from src.application.dto import EvaluationComparisonDTO

# Folga para que uma queda exatamente igual a tolerancia nao seja reprovada
# por erro de arredondamento de ponto flutuante.
_FLOAT_SLACK = 1e-9


@dataclass(frozen=True, slots=True)
class CompareEvaluationReportsInput:
    current: dict[str, float | None]
    previous: dict[str, float | None] | None
    tolerance: float = 0.02


class CompareEvaluationReportsUseCase:
    """Aponta as metricas que regrediram alem da tolerancia (RN-14)."""

    def execute(
        self,
        data: CompareEvaluationReportsInput,
    ) -> EvaluationComparisonDTO:
        if data.tolerance < 0:
            raise ValueError("tolerance must not be negative.")
        deltas = _deltas(data.current, data.previous or {})
        regressions = tuple(
            name
            for name, delta in deltas.items()
            if -delta > data.tolerance + _FLOAT_SLACK
        )
        return EvaluationComparisonDTO(
            deltas=deltas,
            regressions=regressions,
            tolerance=data.tolerance,
        )


def _deltas(
    current: dict[str, float | None],
    previous: dict[str, float | None],
) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for name, value in current.items():
        baseline = previous.get(name)
        if value is None or baseline is None:
            continue
        deltas[name] = value - baseline
    return deltas
