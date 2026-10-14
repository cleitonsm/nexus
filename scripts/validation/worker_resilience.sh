#!/usr/bin/env bash
# CT-53 (RNF-27, C9): resiliencia do worker.
#
# Parte 1 - `docker kill` no worker no meio de um job: o job volta a fila depois
#           do limite (INGESTION_JOB_TIMEOUT_SECONDS, reduzido para 30 s so neste
#           roteiro) e termina sem trechos duplicados.
# Parte 2 - `docker compose stop` (SIGTERM): o job em andamento e concluido
#           antes de o worker sair.
#
# Pre-requisito: pilha no ar (docker compose up -d). Uso, na raiz:
#   scripts/validation/worker_resilience.sh
set -uo pipefail

cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1

OUT="docs/qa/relatorios/$(date +%Y-%m-%d)-ct53"
WORK="tmp/ct53"
mkdir -p "$OUT" "$WORK"
LOG="$OUT/ct53.log"
: > "$LOG"

cat > "$WORK/override.yaml" <<'YAML'
services:
  worker:
    environment:
      INGESTION_JOB_TIMEOUT_SECONDS: "30"
YAML
COMPOSE=(docker compose -f compose.yaml -f "$WORK/override.yaml")

driver() {
  "${COMPOSE[@]}" run --rm --no-deps \
    -v ./backend/tests/integration:/app/integration:ro \
    -v ./scripts:/app/scripts:ro \
    backend python /app/scripts/validation/ct53_driver.py "$@"
}

log() { echo "$*" | tee -a "$LOG"; }
result=0

log "== Parte 1: kill -9 no worker durante o job"
"${COMPOSE[@]}" up -d worker >> "$LOG" 2>&1
sleep 5
started=$(driver start --seed 531 2>&1 | tee -a "$LOG")
assistant=$(echo "$started" | sed -n 's/^ASSISTANT=//p' | tr -d '\r')
document=$(echo "$started" | sed -n 's/^DOCUMENT=//p' | tr -d '\r')
if [ -z "$document" ]; then
  log "FALHA: nao foi possivel iniciar o job"; result=1
else
  "${COMPOSE[@]}" kill worker >> "$LOG" 2>&1
  log "worker encerrado a forca; aguardando o limite de 30 s"
  sleep 35
  "${COMPOSE[@]}" up -d worker >> "$LOG" 2>&1
  if driver wait --document "$document" --assistant "$assistant" --timeout 300 2>&1 | tee -a "$LOG" | grep -q '^OK'; then
    log "OK: job reprocessado sem duplicidade"
  else
    log "FALHA: parte 1"; result=1
  fi
  driver cleanup --assistant "$assistant" >> "$LOG" 2>&1
fi

log "== Parte 2: SIGTERM (docker compose stop) durante o job"
"${COMPOSE[@]}" up -d worker >> "$LOG" 2>&1
sleep 5
started=$(driver start --seed 532 2>&1 | tee -a "$LOG")
assistant=$(echo "$started" | sed -n 's/^ASSISTANT=//p' | tr -d '\r')
document=$(echo "$started" | sed -n 's/^DOCUMENT=//p' | tr -d '\r')
if [ -z "$document" ]; then
  log "FALHA: nao foi possivel iniciar o job"; result=1
else
  "${COMPOSE[@]}" stop worker >> "$LOG" 2>&1
  state=$(driver status --document "$document" 2>&1 | tail -1 | tr -d '\r')
  log "estado depois do stop: $state"
  if [ "$state" = "indexado" ]; then
    log "OK: o job em andamento foi concluido antes de o worker sair"
  else
    log "FALHA: esperado indexado, obtido '$state'"; result=1
  fi
  driver cleanup --assistant "$assistant" >> "$LOG" 2>&1
fi

"${COMPOSE[@]}" up -d worker >> "$LOG" 2>&1
rm -rf "$WORK"
if [ "$result" -eq 0 ]; then log "CT-53: APROVADO"; else log "CT-53: REPROVADO (ver $LOG)"; fi
exit "$result"
