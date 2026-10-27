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

# O conjunto ampliado tem perguntas sobre documentos DOCX com tabelas
# (backend/tests/evaluation/fixtures) e usa um assistente proprio, para nao
# alterar a base do conjunto piloto.
EXTRA=()
if [ "$DATASET" = "nexus-docs-ampliado" ]; then
  EXTRA=(--assistant-name "Nexus Docs Ampliado (avaliacao)" --seed-dir /app/evaluation/fixtures)
fi
# SPEC-012: leis e regulamentos ficticios (backend/tests/evaluation/fixtures/normativo),
# tambem com assistente proprio.
if [ "$DATASET" = "normativo-ficticio" ]; then
  EXTRA=(--assistant-name "Nexus Normativo (avaliacao)" --seed-dir /app/evaluation/fixtures/normativo)
fi

docker compose run --rm --no-deps \
  -e GIT_COMMIT="$GIT_COMMIT" \
  -v ./backend/tests/evaluation:/app/evaluation \
  -v ./docs:/app/seed:ro \
  backend python -m src.cli.evaluate \
  --dataset "/app/evaluation/datasets/${DATASET}.jsonl" \
  --reports-dir /app/evaluation/reports \
  --seed-dir /app/seed/negocio \
  --seed-dir /app/seed/arquitetura \
  "${EXTRA[@]}" \
  "$@"
