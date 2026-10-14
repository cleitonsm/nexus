#!/usr/bin/env bash
# Varre a nota minima de relevancia (CT-22) sobre a base do piloto, sem chamar o LLM.
# Requer que scripts/eval.sh ja tenha indexado o piloto.
# Uso: scripts/calibrate.sh [conjunto] [opcoes do comando]
set -euo pipefail

cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

DATASET="nexus-docs"
if [ "$#" -gt 0 ] && [ "${1#--}" = "$1" ]; then
  DATASET="$1"
  shift
fi

EXTRA=()
if [ "$DATASET" = "nexus-docs-ampliado" ]; then
  EXTRA=(--assistant-name "Nexus Docs Ampliado (avaliacao)")
fi

docker compose run --rm --no-deps \
  -v ./backend/tests/evaluation:/app/evaluation \
  backend python -m src.cli.calibrate_relevance \
  --dataset "/app/evaluation/datasets/${DATASET}.jsonl" \
  --output "/app/evaluation/reports/${DATASET}/calibracao.json" \
  "${EXTRA[@]}" \
  "$@"
