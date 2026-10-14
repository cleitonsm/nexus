"""Consolida os CSVs de medicao em p50, p95, p99, maximo e taxa de erro.

Uso: ``python report.py ARQUIVO.csv[:LIMITE_S[:TIPO]] ... [--out 07-desempenho.md]``

``LIMITE_S`` e o criterio em segundos; ``TIPO`` e ``all`` (todas as amostras
devem cumprir, padrao) ou ``p95`` (so o percentil 95 deve cumprir). Sem limite o
cenario e informativo. Saida com codigo 1 se algum criterio falhar.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:  # executado como script ou importado pelos testes
    from common import Sample, is_success, percentile, read_samples
except ImportError:  # pragma: no cover
    from scripts.perf.common import Sample, is_success, percentile, read_samples


@dataclass(frozen=True)
class Summary:
    name: str
    samples: int
    p50: float
    p95: float
    p99: float
    maximum: float
    error_rate: float
    limit_s: float | None
    rule: str
    verdict: str


def summarize(
    name: str,
    samples: list[Sample],
    limit_s: float | None = None,
    rule: str = "all",
) -> Summary:
    if rule not in ("all", "p95"):
        raise ValueError("rule must be 'all' or 'p95'.")
    if not samples:
        raise ValueError(f"{name}: no samples.")
    durations = [s.duration_s for s in samples]
    errors = sum(1 for s in samples if not is_success(s.status))
    p95 = percentile(durations, 0.95)
    maximum = max(durations)
    if limit_s is None:
        verdict = "informativo"
    else:
        measured = maximum if rule == "all" else p95
        verdict = "aprovado" if measured <= limit_s and errors == 0 else "reprovado"
    return Summary(
        name=name,
        samples=len(samples),
        p50=percentile(durations, 0.50),
        p95=p95,
        p99=percentile(durations, 0.99),
        maximum=maximum,
        error_rate=errors / len(samples),
        limit_s=limit_s,
        rule=rule,
        verdict=verdict,
    )


def to_markdown(summaries: list[Summary]) -> str:
    lines = [
        "| Cenário | Amostras | p50 (s) | p95 (s) | p99 (s) | Máx. (s) | Erros | Critério | Veredito |",
        "|---------|---------:|--------:|--------:|--------:|---------:|------:|----------|----------|",
    ]
    for item in summaries:
        criterion = (
            "—"
            if item.limit_s is None
            else f"{'todas' if item.rule == 'all' else 'p95'} ≤ {item.limit_s:g} s"
        )
        lines.append(
            f"| {item.name} | {item.samples} | {item.p50:.3f} | {item.p95:.3f} | "
            f"{item.p99:.3f} | {item.maximum:.3f} | {item.error_rate:.1%} | "
            f"{criterion} | {item.verdict} |"
        )
    return "\n".join(lines) + "\n"


def parse_spec(spec: str) -> tuple[Path, float | None, str]:
    path, *rest = spec.split(":")
    limit = float(rest[0]) if rest and rest[0] else None
    rule = rest[1] if len(rest) > 1 else "all"
    return Path(path), limit, rule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("specs", nargs="+")
    parser.add_argument("--out", help="grava a tabela em Markdown")
    args = parser.parse_args(argv)
    summaries = []
    for spec in args.specs:
        path, limit, rule = parse_spec(spec)
        summaries.append(summarize(path.stem, read_samples(path), limit, rule))
    table = to_markdown(summaries)
    print(table)
    if args.out:
        Path(args.out).write_text(table, encoding="utf-8")
    return 1 if any(item.verdict == "reprovado" for item in summaries) else 0


if __name__ == "__main__":
    sys.exit(main())
