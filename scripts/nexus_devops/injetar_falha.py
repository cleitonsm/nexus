"""Injecao de falha controlada no Nexus (ADR 0015).

Cada cenario troca um trecho exato do codigo por uma versao sintaticamente
correta, mas defeituosa, que o pipeline ``nexus-devops`` deve pegar. O agente
de IA entao comenta a causa-raiz no pull request.

Serve para validar o agente com erros conhecidos. Uso, na raiz do
repositorio, numa branch descartavel:

    git switch -c chaos/falha-tipo
    python scripts/nexus_devops/injetar_falha.py tipo
    git commit -am "chaos: falha controlada (tipo)" && git push -u origin HEAD
    gh pr create --fill --base main

Para desfazer: ``python scripts/nexus_devops/injetar_falha.py tipo --reverter``.
Nunca faca merge de uma branch ``chaos/``.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Scenario:
    name: str
    path: str
    original: str
    faulty: str
    stage: str
    expected: str


SCENARIOS: dict[str, Scenario] = {
    # Erro de tipo que so aparece na execucao: o custo estimado do LLM passa a
    # dividir um Decimal por um texto vindo "da configuracao".
    "tipo": Scenario(
        name="tipo",
        path="backend/src/domain/usage.py",
        original=") / Decimal(1000)\n",
        faulty=') / "1000"  # falha controlada: divisor lido como texto\n',
        stage="unit_test",
        expected="TypeError: unsupported operand type(s) for /: 'decimal.Decimal' and 'str'",
    ),
    # Erro de logica: compila, roda e devolve um custo 10x maior.
    "logica": Scenario(
        name="logica",
        path="backend/src/domain/usage.py",
        original=") / Decimal(1000)\n",
        faulty=") / Decimal(100)  # falha controlada: preco por cem tokens\n",
        stage="unit_test",
        expected="AssertionError em test_cost_is_estimated_per_thousand_tokens",
    ),
    # Quebra o estagio de build/lint (ruff F401) antes dos testes.
    "lint": Scenario(
        name="lint",
        path="backend/src/domain/usage.py",
        original="from dataclasses import dataclass, field\n",
        faulty="import json  # falha controlada: import sem uso\nfrom dataclasses import dataclass, field\n",
        stage="lint",
        expected="F401 `json` imported but unused",
    ),
    # Seguranca: intersecao vira uniao e qualquer usuario passa no filtro de
    # grupos do documento (RN-23). A IA deve apontar o risco de vazamento.
    "isolamento": Scenario(
        name="isolamento",
        path="backend/src/domain/access.py",
        original="return not document_groups or bool(user_groups & document_groups)\n",
        faulty="return not document_groups or bool(user_groups | document_groups)\n",
        stage="unit_test",
        expected="AssertionError em test_access_control (documento restrito visivel a outro grupo)",
    ),
}


class InjectionError(RuntimeError):
    pass


def apply(scenario: Scenario, root: Path = ROOT, revert: bool = False) -> Path:
    target = root / scenario.path
    # Sem traducao de fim de linha: checkout no Windows (CRLF) fica como esta.
    with open(target, encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = "\r\n" if "\r\n" in text else "\n"
    original, faulty = (s.replace("\n", eol) for s in (scenario.original, scenario.faulty))
    if not revert and faulty in text:
        raise InjectionError(f"a falha '{scenario.name}' ja esta aplicada em {scenario.path}.")
    old, new = (faulty, original) if revert else (original, faulty)
    count = text.count(old)
    if count != 1:
        raise InjectionError(
            f"trecho esperado aparece {count} vezes em {scenario.path}; "
            "o codigo mudou ou o cenario ja foi revertido."
        )
    with open(target, "w", encoding="utf-8", newline="") as handle:
        handle.write(text.replace(old, new))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Injeta uma falha controlada no Nexus.")
    parser.add_argument("cenario", choices=sorted(SCENARIOS))
    parser.add_argument("--reverter", action="store_true", help="desfaz a falha")
    parser.add_argument("--raiz", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    scenario = SCENARIOS[args.cenario]
    try:
        path = apply(scenario, args.raiz, revert=args.reverter)
    except InjectionError as error:
        sys.stderr.write(f"erro: {error}\n")
        return 1
    action = "revertida" if args.reverter else "injetada"
    sys.stdout.write(
        f"Falha '{scenario.name}' {action} em {path.relative_to(args.raiz)}.\n"
        f"Estagio que deve falhar: {scenario.stage}\nErro esperado: {scenario.expected}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
