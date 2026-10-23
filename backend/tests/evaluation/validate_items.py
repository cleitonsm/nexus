"""Registra a validacao do curador nos itens de um conjunto de referencia (RN-15).

Uso (so biblioteca padrao):

  python validate_items.py datasets/nexus-docs-ampliado.jsonl --list
  python validate_items.py datasets/nexus-docs-ampliado.jsonl --by "Nome" --approve te-01 te-02
  python validate_items.py datasets/nexus-docs-ampliado.jsonl --by "Nome" --approve-all

``--list`` mostra os itens ainda sem ``validated_by``. Aprovar um item preenche o campo e
remove a marca ``origem`` de rascunho. Quem aprova assume que leu a pergunta, a resposta
esperada e as fontes; para corrigir um item, edite o arquivo antes de aprovar.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def pending(items: list[dict]) -> list[dict]:
    return [item for item in items if not str(item.get("validated_by") or "").strip()]


def approve(items: list[dict], ids: set[str] | None, by: str) -> list[str]:
    """Aprova os itens pendentes (todos se ``ids`` for None); devolve os ids aprovados."""
    if not by.strip():
        raise ValueError("--by must not be empty.")
    approved = []
    for item in pending(items):
        if ids is None or item["id"] in ids:
            item["validated_by"] = by.strip()
            item.pop("origem", None)
            approved.append(item["id"])
    unknown = (ids or set()) - {item["id"] for item in items}
    if unknown:
        raise ValueError(f"unknown ids: {', '.join(sorted(unknown))}")
    return approved


def save(path: Path, items: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items),
        encoding="utf-8",
        newline="\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--by")
    parser.add_argument("--approve", nargs="+")
    parser.add_argument("--approve-all", action="store_true")
    args = parser.parse_args(argv)

    items = load(args.dataset)
    if args.list or not (args.approve or args.approve_all):
        waiting = pending(items)
        for item in waiting:
            kind = "fora do escopo" if item.get("out_of_scope") else "dentro do escopo"
            print(f"{item['id']:8} [{kind}] {item['question']}")
        print(f"{len(waiting)} de {len(items)} itens aguardam validacao")
        return 0
    if not args.by:
        parser.error("--by e obrigatorio para aprovar")
    try:
        approved = approve(items, None if args.approve_all else set(args.approve), args.by)
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    save(args.dataset, items)
    print(f"{len(approved)} itens aprovados por {args.by}; restam {len(pending(items))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
