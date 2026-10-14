"""PreToolUse: bloqueia acesso a segredos e reescrita de migracoes aplicadas.

Regras (ADR 0011 e limites do agente desenvolvedor):
- `.env` e `.env.*` (exceto `.env.example`) nao podem ser lidos nem gravados.
- Migracao existente em `alembic/versions/` nao pode ser editada nem
  sobrescrita; mudanca de esquema = nova migracao numerada.

Saida 2 bloqueia a ferramenta e devolve a mensagem ao Claude.
So usa a biblioteca padrao, para rodar igual no Windows e no Linux.
"""

from __future__ import annotations

import json
import os
import re
import sys

FILE_TOOLS = {"Read", "Edit", "MultiEdit", "Write", "NotebookEdit"}
WRITE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
# `.env` ou `.env.<algo>` como palavra isolada; `.env.example` liberado;
# `process.env.X` nao casa (ha letra antes do ponto).
ENV_IN_COMMAND = re.compile(r"(?<![\w.])\.env(?!\.example\b)(?:\.[\w-]+)?(?![\w-])")


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def is_secret_file(path: str) -> bool:
    name = os.path.basename(path.replace("\\", "/"))
    if name == ".env.example":
        return False
    return name == ".env" or name.startswith(".env.")


def is_existing_migration(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return "/alembic/versions/" in normalized and normalized.endswith(".py") and os.path.isfile(path)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if path and is_secret_file(path):
            block(
                f"Bloqueado: '{path}' guarda segredos locais. Use .env.example "
                "para documentar variaveis; nunca leia nem grave .env."
            )
        if tool in WRITE_TOOLS and path and is_existing_migration(path):
            block(
                f"Bloqueado: '{path}' e uma migracao ja existente (ADR 0011). "
                "Crie uma nova migracao numerada (use /new-migration) em vez de "
                "alterar uma revisao que pode ja estar aplicada."
            )

    if tool == "Bash":
        command = tool_input.get("command", "")
        if ENV_IN_COMMAND.search(command):
            block(
                "Bloqueado: o comando referencia um arquivo .env com segredos. "
                "Use .env.example ou peca ao usuario o valor necessario."
            )


if __name__ == "__main__":
    main()
