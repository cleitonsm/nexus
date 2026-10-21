"""V6: confere os relatorios de avaliacao contra as metas da secao 6.3 do plano de validacao.

Uso (biblioteca padrao):

  python check_eval_reports.py backend/tests/evaluation/reports/nexus-docs-ampliado --runs 3
  python check_eval_reports.py DIR --runs 1 --only-generation   # depois de cada execucao

Le os ``--runs`` relatorios mais recentes (``*.json``, exceto ``calibracao.json``) e exige:

* modelo do relatorio igual ao oficial (``--model``, decisao PC-D8);
* conjunto validado pelo curador (``validated``) e geracao feita (fidelidade calculada); sem a
  chave do LLM a avaliacao pula a geracao so com um aviso, e isso nao pode passar por aprovacao;
* recall@5 >= 0,80 em cada execucao (RNF-19);
* fidelidade >= 0,90 na media e nenhuma execucao abaixo de 0,88 (RNF-20);
* fallback fora do escopo >= 0,90 em cada execucao (RNF-21);
* cobertura de citacoes = 100% em cada execucao (RF-37).

A regressao do MRR entre execucoes (RN-14) ja reprova a propria avaliacao (codigo 1).
Codigo de saida: 0 metas atingidas; 1 meta nao atingida; 2 relatorio ausente ou sem geracao.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPORT_NAME = re.compile(r"^\d{8}-\d{6}-.+\.json$")
RECALL_MIN = 0.80
FAITHFULNESS_MEAN_MIN = 0.90
FAITHFULNESS_RUN_MIN = 0.88
FALLBACK_MIN = 0.90
CITATION_MIN = 1.0


def latest_reports(directory: Path, runs: int) -> list[dict]:
    # So os relatorios (AAAAMMDD-HHMMSS-<commit>.json), como o JsonEvaluationReportStore.
    files = sorted(
        (path for path in directory.glob("*.json") if REPORT_NAME.match(path.name)),
        key=lambda path: path.name,
    )
    return [json.loads(path.read_text(encoding="utf-8")) | {"_file": path.name} for path in files[-runs:]]


def invalid(reports: list[dict], runs: int, model: str | None = None) -> list[str]:
    problems = []
    if len(reports) < runs:
        problems.append(f"esperados {runs} relatorios, encontrados {len(reports)}")
    for report in reports:
        name = report["_file"]
        if not report.get("validated"):
            problems.append(f"{name}: conjunto nao validado pelo curador")
        if report.get("metrics", {}).get("faithfulness") is None:
            problems.append(
                f"{name}: sem geracao (fidelidade ausente); cadastre a chave do LLM na tela de "
                "Administracao e repita a V6"
            )
        used = report.get("parameters", {}).get("llm_model")
        if model and used != model:
            problems.append(
                f"{name}: gerado com o modelo {used!r}, nao com o oficial {model!r} "
                "(confira a conexao do LLM na tela de Administracao)"
            )
    return problems


def failures(reports: list[dict]) -> list[str]:
    problems = []
    faithfulness = []
    for report in reports:
        name, metrics = report["_file"], report["metrics"]
        recall = metrics.get("recall_at_k") or 0.0
        fallback = metrics.get("fallback_accuracy")
        citation = metrics.get("citation_coverage")
        faithfulness.append(metrics["faithfulness"])
        if recall < RECALL_MIN:
            problems.append(f"{name}: recall@5 {recall:.3f} < {RECALL_MIN}")
        if metrics["faithfulness"] < FAITHFULNESS_RUN_MIN:
            problems.append(f"{name}: fidelidade {metrics['faithfulness']:.3f} < {FAITHFULNESS_RUN_MIN}")
        if fallback is None or fallback < FALLBACK_MIN:
            problems.append(f"{name}: fallback {fallback} < {FALLBACK_MIN}")
        if citation is None or citation < CITATION_MIN:
            problems.append(f"{name}: cobertura de citacoes {citation} < {CITATION_MIN}")
    if faithfulness:
        mean = sum(faithfulness) / len(faithfulness)
        if mean < FAITHFULNESS_MEAN_MIN:
            problems.append(f"fidelidade media {mean:.3f} < {FAITHFULNESS_MEAN_MIN}")
    return problems


def table(reports: list[dict]) -> str:
    lines = ["| Relatorio | recall@5 | MRR | fidelidade | fallback | citacoes |", "|---|---|---|---|---|---|"]
    for report in reports:
        m = report.get("metrics", {})
        cells = [m.get(key) for key in ("recall_at_k", "mrr", "faithfulness", "fallback_accuracy", "citation_coverage")]
        lines.append(
            f"| {report['_file']} | "
            + " | ".join("n/d" if value is None else f"{value:.3f}" for value in cells)
            + " |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--only-generation", action="store_true", help="so confere se houve geracao")
    parser.add_argument("--model", default=None, help="modelo oficial exigido (PC-D8)")
    args = parser.parse_args(argv)
    reports = latest_reports(args.directory, args.runs)
    print(table(reports))
    problems = invalid(reports, args.runs, args.model)
    if problems:
        print("\n".join(["INVALIDO:"] + problems))
        return 2
    if args.only_generation:
        return 0
    problems = failures(reports)
    if problems:
        print("\n".join(["METAS NAO ATINGIDAS:"] + problems))
        return 1
    print("OK: metas de qualidade atingidas nas execucoes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
