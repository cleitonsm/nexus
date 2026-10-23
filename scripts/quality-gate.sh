#!/usr/bin/env bash
# Portao de qualidade local (SPEC-006: RF-62, RN-14; D4).
#
# Roda o que a integracao continua do GitHub nao roda por depender do
# ambiente completo e, na fidelidade, de LLM com a API key configurada:
#   1. testes unitarios dentro da imagem do backend;
#   2. avaliacao de recuperacao (recall@k e MRR), sempre;
#   3. avaliacao completa com fidelidade (consome LLM), so com --fidelidade.
# Termina com erro quando ha regressao acima de EVAL_REGRESSION_TOLERANCE
# em relacao ao ultimo relatorio do conjunto.
#
# Uso: scripts/quality-gate.sh [--fidelidade] [conjunto]
set -euo pipefail

cd "$(dirname "$0")/.."
export MSYS_NO_PATHCONV=1

FIDELITY=0
DATASET="nexus-docs"
for arg in "$@"; do
  case "$arg" in
    --fidelidade) FIDELITY=1 ;;
    *) DATASET="$arg" ;;
  esac
done

echo "== testes unitarios"
# scripts/ e docs/ na raiz do container (/): alguns testes leem a raiz do repositorio,
# um nivel acima de /app (a pasta backend), como na V2 do run-all.
docker compose run --rm --no-deps \
  -v ./backend/tests:/app/tests:ro -v ./scripts:/scripts:ro -v ./docs:/docs:ro \
  backend python -m unittest discover -s tests/unit

echo "== avaliacao de recuperacao (${DATASET})"
scripts/eval.sh "$DATASET" --no-generation

if [ "$FIDELITY" -eq 1 ]; then
  echo "== avaliacao completa com fidelidade (${DATASET})"
  scripts/eval.sh "$DATASET"
fi
echo "== portao de qualidade aprovado"
