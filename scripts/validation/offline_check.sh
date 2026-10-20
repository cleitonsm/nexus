#!/usr/bin/env bash
# CT-54 (RNF-26): a pilha funciona sem rede externa.
#
# Reinicia o backend, o worker e os servicos de apoio numa rede `internal` do
# Compose (sem saida para a internet) com HF_HUB_OFFLINE=1 e TRANSFORMERS_OFFLINE=1,
# confere que a internet esta mesmo inacessivel e executa ingestao, busca e
# reranking (avaliacao sem LLM) e o OCR de um PDF digitalizado. Os modelos ja
# precisam estar no volume de cache (rode a pilha online ao menos uma vez).
#
# Requer Docker Compose 2.24 ou superior (`!override`). Pre-requisito: pilha
# ja construida. Uso, na raiz:
#   scripts/validation/offline_check.sh [conjunto]
set -uo pipefail

cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1

DATASET="${1:-nexus-docs}"
OUT="docs/qa/relatorios/$(date +%Y-%m-%d)-ct54"
WORK="tmp/ct54"
mkdir -p "$OUT" "$WORK"
LOG="$OUT/ct54.log"
: > "$LOG"

cat > "$WORK/override.yaml" <<'YAML'
networks:
  offline:
    internal: true
services:
  postgres: { networks: !override [offline] }
  qdrant: { networks: !override [offline] }
  keycloak: { networks: !override [offline] }
  keycloak-db-init: { networks: !override [offline] }
  backend:
    networks: !override [offline]
    environment: { HF_HUB_OFFLINE: "1", TRANSFORMERS_OFFLINE: "1" }
  worker:
    networks: !override [offline]
    environment: { HF_HUB_OFFLINE: "1", TRANSFORMERS_OFFLINE: "1" }
YAML
COMPOSE=(docker compose -f compose.yaml -f "$WORK/override.yaml")

log() { echo "$*" | tee -a "$LOG"; }
result=0

# Volta a pilha a rede normal e so termina com ela saudavel: o item seguinte da
# V3 (CT-56) usa a API logo em seguida ("Connection refused" em 2026-10-20).
restore() {
  docker compose up -d --wait >> "$LOG" 2>&1 \
    || echo "AVISO: a pilha nao ficou saudavel depois do CT-54" | tee -a "$LOG"
  rm -rf "$WORK"
}
trap restore EXIT

log "== Subindo a pilha na rede interna"
"${COMPOSE[@]}" up -d --force-recreate postgres qdrant keycloak backend worker >> "$LOG" 2>&1 \
  || { log "FALHA: a pilha nao subiu na rede interna"; exit 1; }
sleep 20

log "== A internet deve estar inacessivel"
if "${COMPOSE[@]}" exec -T backend python -c \
  "import urllib.request; urllib.request.urlopen('https://huggingface.co', timeout=5)" >> "$LOG" 2>&1; then
  log "FALHA: o container alcancou a internet; o isolamento nao esta valendo"; exit 1
fi
log "OK: sem saida para a internet"

log "== Ingestao, busca e reranking (avaliacao sem LLM)"
"${COMPOSE[@]}" run --rm --no-deps \
  -e GIT_COMMIT=ct54 \
  -v ./backend/tests/evaluation:/app/evaluation \
  -v ./docs:/app/seed:ro \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
  backend python -m src.cli.evaluate \
  --dataset "/app/evaluation/datasets/${DATASET}.jsonl" \
  --reports-dir "/app/evaluation/reports" \
  --assistant-name "CT-54 offline" \
  --seed-dir /app/seed/negocio --seed-dir /app/seed/arquitetura \
  --no-generation >> "$LOG" 2>&1
code=$?
# Codigo 1 e regressao frente a um relatorio anterior; so 2 e 3 sao falha de execucao.
if [ "$code" -eq 0 ] || [ "$code" -eq 1 ]; then
  log "OK: avaliacao sem LLM terminou (codigo $code)"
else
  log "FALHA: avaliacao terminou com codigo $code"; result=1
fi

log "== OCR de PDF digitalizado"
if "${COMPOSE[@]}" run --rm --no-deps \
  -v ./backend/tests/integration:/app/integration:ro \
  -e HF_HUB_OFFLINE=1 \
  backend sh -c "cd /app/integration && python -m unittest -v test_ocr_container" >> "$LOG" 2>&1; then
  log "OK: OCR"
else
  log "FALHA: OCR"; result=1
fi

# Remove o assistente criado pela avaliacao (nome proprio deste roteiro).
log "(o assistente 'CT-54 offline' pode ser excluido pela interface)"
if [ "$result" -eq 0 ]; then log "CT-54: APROVADO"; else log "CT-54: REPROVADO (ver $LOG)"; fi
exit "$result"
