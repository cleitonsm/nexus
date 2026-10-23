"""Texto e JSON do relatorio de calibracao (sem dependencias de infraestrutura)."""

from __future__ import annotations

from src.application.use_cases import CalibrationReport


def format_report(report: CalibrationReport) -> str:
    lines = [
        f"Nota minima atual: {report.current_threshold:.2f}",
        "",
        "nota | responde (dentro do escopo) | recusa (fora do escopo) | media",
        "-----|-----------------------------|-------------------------|------",
    ]
    for point in report.points:
        marker = " <- atual" if point.threshold == report.current_threshold else ""
        lines.append(
            f"{point.threshold:.2f} | {_pct(point.answered_in_scope):>27} | "
            f"{_pct(point.refused_out_of_scope):>23} | {_pct(point.balanced):>5}"
            f"{marker}"
        )
    if report.best is not None:
        lines += [
            "",
            f"Maior media: {report.best.threshold:.2f} "
            f"({_pct(report.best.balanced)}). Referencia para a decisao, nao "
            "valor aplicado.",
        ]
    lines += ["", "Itens com a fonte esperada abaixo de 0,50 ou ausente:"]
    weak = [
        item
        for item in report.items
        if not item.out_of_scope
        and (item.source_score is None or item.source_score < 0.5)
    ]
    lines += [
        f"  {item.item_id}: fonte={_score(item.source_score)} "
        f"topo={_score(item.top_score)}"
        for item in weak
    ] or ["  nenhum"]
    lines += ["", "Fora do escopo com nota alta (>= 0,30):"]
    noisy = [
        item
        for item in report.items
        if item.out_of_scope and (item.top_score or 0.0) >= 0.3
    ]
    lines += [
        f"  {item.item_id}: topo={_score(item.top_score)}" for item in noisy
    ] or ["  nenhum"]
    return "\n".join(lines)


def to_dict(report: CalibrationReport) -> dict[str, object]:
    return {
        "current_threshold": report.current_threshold,
        "best_threshold": report.best.threshold if report.best else None,
        "points": [
            {
                "threshold": p.threshold,
                "answered_in_scope": p.answered_in_scope,
                "refused_out_of_scope": p.refused_out_of_scope,
                "balanced": p.balanced,
            }
            for p in report.points
        ],
        "items": [
            {
                "id": i.item_id,
                "out_of_scope": i.out_of_scope,
                "top_score": i.top_score,
                "source_score": i.source_score,
            }
            for i in report.items
        ],
    }


def _pct(value: float | None) -> str:
    return "n/d" if value is None else f"{value * 100:.0f}%"


def _score(value: float | None) -> str:
    return "n/d" if value is None else f"{value:.2f}"
