from __future__ import annotations

import json
from pathlib import Path


class JsonEvaluationReportStore:
    """Grava cada relatorio em JSON, com um resumo em Markdown ao lado."""

    def __init__(self, base_directory: Path) -> None:
        self._base_directory = base_directory

    def load_latest(self, dataset_name: str) -> dict[str, object] | None:
        directory = self._base_directory / dataset_name
        if not directory.is_dir():
            return None
        reports = sorted(directory.glob("*.json"))
        if not reports:
            return None
        return json.loads(reports[-1].read_text(encoding="utf-8"))

    def save(
        self,
        dataset_name: str,
        report: dict[str, object],
        *,
        label: str,
        deltas: dict[str, float] | None = None,
        regressions: tuple[str, ...] = (),
    ) -> Path:
        directory = self._base_directory / dataset_name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{label}.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary = _render_summary(report, deltas or {}, regressions)
        path.with_suffix(".md").write_text(summary, encoding="utf-8")
        return path


def _render_summary(
    report: dict[str, object],
    deltas: dict[str, float],
    regressions: tuple[str, ...],
) -> str:
    metrics = report.get("metrics") or {}
    parameters = report.get("parameters") or {}
    lines = [
        "# Relatorio de avaliacao",
        "",
        f"- Assistente: `{report.get('assistant_id')}`",
        f"- Gerado em: {report.get('created_at')}",
        f"- k: {report.get('k')}",
        f"- Conjunto validado por curador: {'sim' if report.get('validated') else 'nao'}",
        "",
        "## Metricas",
        "",
        "| Metrica | Valor | Variacao |",
        "|---|---|---|",
    ]
    for name, value in metrics.items():
        lines.append(f"| {name} | {_number(value)} | {_delta(deltas.get(name))} |")
    lines += ["", "## Parametros", ""]
    lines += [f"- {name}: `{value}`" for name, value in parameters.items()]
    lines += ["", "## Regressoes", ""]
    lines.append(", ".join(regressions) if regressions else "Nenhuma.")
    return "\n".join(lines) + "\n"


def _number(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.3f}"
    return "n/d"


def _delta(value: float | None) -> str:
    if value is None:
        return "n/d"
    return f"{value:+.3f}"
