#!/usr/bin/env bash
# CT-48 (SPEC-006: RF-62, RN-14): uma regressao simulada faz o portao de
# qualidade falhar.
#
# Copia backend/tests/evaluation para tmp/ct48/, acrescenta um relatorio
# anterior com metricas impossiveis de igualar (recall@k e MRR = 1,0, mais
# recente que qualquer relatorio real) e roda a mesma avaliacao de recuperacao
# do scripts/quality-gate.sh (--no-generation, sem LLM). O CT-48 passa quando
# a avaliacao termina com o codigo de regressao (1) e o novo relatorio aponta
# a regressao. Os relatorios reais nao sao tocados.
#
# Pre-requisito: ambiente no ar (docker compose up -d). Uso, na raiz:
#   scripts/validation/regression-gate.sh [conjunto]
set -uo pipefail

cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1

DATASET="${1:-nexus-docs}"
EXIT_REGRESSION=1
WORK="tmp/ct48"
OUT="docs/qa/relatorios/$(date +%Y-%m-%d)-ct48"
BASELINE_LABEL="29991231-235959-ct48-baseline"

rm -rf "$WORK"
mkdir -p "$WORK" "$OUT"
cp -r backend/tests/evaluation "$WORK/evaluation"
mkdir -p "$WORK/evaluation/reports/$DATASET"
cat > "$WORK/evaluation/reports/$DATASET/$BASELINE_LABEL.json" <<'EOF'
{
  "note": "Relatorio ficticio do CT-48: linha de base impossivel de igualar.",
  "metrics": {"recall_at_k": 1.0, "mrr": 1.0}
}
EOF

docker compose run --rm --no-deps \
  -e GIT_COMMIT=ct48 \
  -v "./$WORK/evaluation:/app/evaluation" \
  -v ./docs:/app/seed:ro \
  backend python -m src.cli.evaluate \
  --dataset "/app/evaluation/datasets/${DATASET}.jsonl" \
  --reports-dir /app/evaluation/reports \
  --seed-dir /app/seed/negocio \
  --seed-dir /app/seed/arquitetura \
  --no-generation > "$OUT/avaliacao.log" 2>&1
status=$?

latest=$(ls -1 "$WORK/evaluation/reports/$DATASET"/*-ct48.md 2>/dev/null | grep -v baseline | tail -1)
[ -n "$latest" ] && cp "$latest" "$OUT/relatorio-com-regressao.md"

if [ "$status" -eq "$EXIT_REGRESSION" ] && [ -n "$latest" ]; then
  result="OK: a avaliacao falhou com codigo $status ao comparar com a linha de base inflada"
  code=0
else
  result="FALHA: codigo $status (esperado $EXIT_REGRESSION); ver avaliacao.log"
  code=1
fi
{
  echo "# CT-48 — regressão simulada"
  echo
  echo "Data: $(date -Iseconds). Commit $(git rev-parse --short HEAD 2>/dev/null || echo desconhecido)."
  echo
  echo "$result"
} > "$OUT/resumo.md"
echo "$result"
rm -rf "$WORK"
exit "$code"
