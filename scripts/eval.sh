#!/usr/bin/env bash
# Executa a avaliacao de qualidade do RAG dentro do container do backend.
# Uso: scripts/eval.sh [conjunto] [opcoes do comando]
set -euo pipefail

cd "$(dirname "$0")/.."

# Impede o Git Bash no Windows de reescrever os caminhos internos do container.
export MSYS_NO_PATHCONV=1

DATASET="nexus-docs"
if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then
  DATASET="$1"
  shift
fi

GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

docker compose run --rm --no-deps \
  -e GIT_COMMIT="$GIT_COMMIT" \
  -v ./backend/tests/evaluation:/app/evaluation \
  -v ./docs:/app/seed:ro \
  backend python -m src.cli.evaluate \
  --dataset "/app/evaluation/datasets/${DATASET}.jsonl" \
  --reports-dir /app/evaluation/reports \
  --seed-dir /app/seed/negocio \
  --seed-dir /app/seed/arquitetura \
  "$@"
