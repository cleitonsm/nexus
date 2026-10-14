"""PostToolUse: roda o ruff com as mesmas regras do CI apos editar Python.

Espelha `ruff check --select F,E9` do .github/workflows/ci.yml (nomes
indefinidos, imports sem uso, erros de sintaxe). Se o ruff nao estiver
instalado, nao faz nada. Saida 2 devolve os erros ao Claude para corrigir.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def ruff_command() -> list[str] | None:
    exe = shutil.which("ruff")
    if exe:
        return [exe]
    probe = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"], capture_output=True, text=True
    )
    return [sys.executable, "-m", "ruff"] if probe.returncode == 0 else None


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return
    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path.endswith(".py"):
        return
    cmd = ruff_command()
    if cmd is None:
        return
    result = subprocess.run(
        [*cmd, "check", "--select", "F,E9", "--quiet", "--no-cache", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            "ruff (mesmas regras do CI) encontrou problemas:\n"
            + (result.stdout or result.stderr),
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
