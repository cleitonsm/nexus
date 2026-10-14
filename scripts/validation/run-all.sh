#!/usr/bin/env bash
# Orquestrador da validacao final (Parte B, V0 a V8). Ver docs/qa/plano-de-validacao-final.md.
#
# Executa as etapas na ordem e PARA na primeira falha bloqueante. Grava os
# registros em docs/qa/relatorios/<data>/ e termina com 0 so se tudo passou.
#
# Uso, na raiz do repositorio:
#   scripts/validation/run-all.sh [--dry-run] [--from V3] [--only V4] [--keep-env]
#
# Variaveis para V7 (desempenho): NEXUS_ASSISTANT_ID, NEXUS_BASE_URL (padrao
# http://localhost:8000), NEXUS_TEST_USER/NEXUS_TEST_PASSWORD (cliente nexus-tests)
# ou NEXUS_TOKEN. V5 (ponta a ponta) e manual: o script registra como pendente.
set -uo pipefail

cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1

DRY_RUN=0
FROM=""
ONLY=""
KEEP_ENV=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --from) FROM="${2:-}"; shift ;;
    --only) ONLY="${2:-}"; shift ;;
    --keep-env) KEEP_ENV=1 ;;
    -h|--help) sed -n 2,14p "$0"; exit 0 ;;
    *) echo "opcao desconhecida: $1" >&2; exit 2 ;;
  esac
  shift
done

STEPS=(V0 V1 V2 V3 V4 V5 V6 V7 V8)
OUT="${NEXUS_REPORT_DIR:-docs/qa/relatorios/$(date +%Y-%m-%d)}"
BASE_URL="${NEXUS_BASE_URL:-http://localhost:8000}"
FAILED=0
PENDING=0
SUMMARY=()

selected() {
  local step="$1"
  if [ -n "$ONLY" ]; then [ "$step" = "$ONLY" ]; return; fi
  if [ -n "$FROM" ]; then
    local reached=0 item
    for item in "${STEPS[@]}"; do
      [ "$item" = "$FROM" ] && reached=1
      [ "$item" = "$step" ] && return $((1 - reached))
    done
  fi
  return 0
}

# run <etapa> <descricao> <comando...>: executa, registra e conta a falha.
run() {
  local step="$1" label="$2"; shift 2
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[$step] $label :: $*"
    return 0
  fi
  mkdir -p "$OUT"
  local log="$OUT/${step}-$(echo "$label" | tr -c 'A-Za-z0-9' '-' | cut -c1-40).log"
  echo "[$step] $label"
  if "$@" >"$log" 2>&1; then
    SUMMARY+=("| $step | $label | OK |")
  else
    SUMMARY+=("| $step | $label | FALHA ($log) |")
    FAILED=1
    return 1
  fi
}

# pending <etapa> <descricao> <motivo>: item que nao pode ser executado aqui.
pending() {
  local step="$1" label="$2" reason="$3"
  if [ "$DRY_RUN" -eq 1 ]; then echo "[$step] $label :: PENDENTE ($reason)"; return 0; fi
  SUMMARY+=("| $step | $label | PENDENTE: $reason |")
  PENDING=1
}

# run_script <etapa> <descricao> <arquivo> [args]: roda se o arquivo existir.
run_script() {
  local step="$1" label="$2" file="$3"; shift 3
  if [ -f "$file" ] || [ "$DRY_RUN" -eq 1 ]; then
    run "$step" "$label" bash "$file" "$@"
  else
    pending "$step" "$label" "script ausente: $file"
  fi
}

stage_v0() {
  run V0 "snapshot do ambiente" bash scripts/validation/env_snapshot.sh "$OUT/00-ambiente.md" || return 1
  run V0 "varredura de depuracao (agent log / 127.0.0.1:7657)" \
    bash -c '! git grep -nE "#region agent log|127\.0\.0\.1:7657" -- . ":(exclude)docs" ":(exclude)scripts/validation"' || return 1
  run V0 "varredura de bypassSecurityTrustHtml" \
    bash -c '! git grep -n "bypassSecurityTrustHtml" -- frontend/src' || return 1
  run V0 ".env fora do Git" bash -c '! git ls-files --error-unmatch .env >/dev/null 2>&1' || return 1
  if [ "$KEEP_ENV" -eq 0 ]; then
    run V0 "ambiente limpo (down -v)" docker compose down -v || return 1
  fi
}

stage_v1() {
  run V1 "subida com healthchecks (up --build --wait)" docker compose up -d --build --wait || return 1
  run V1 "revisao das migracoes" docker compose exec -T backend alembic current || return 1
}

stage_v2() {
  run V2 "testes unitarios no container" docker compose run --rm --no-deps \
    -v ./backend/tests:/app/tests backend python -m unittest discover -s tests/unit -v
}

stage_v3() {
  run V3 "testes de integracao do backend" docker compose run --rm \
    -v ./backend/tests:/app/tests backend python -m unittest discover -s tests/integration -v || return 1
  run_script V3 "CT-53 resiliencia do worker" scripts/validation/worker_resilience.sh || return 1
  run_script V3 "CT-54 operacao offline" scripts/validation/offline_check.sh || return 1
  if [ -f scripts/validation/leakage_scan.py ] || [ "$DRY_RUN" -eq 1 ]; then
    run V3 "CT-56 varredura de vazamento" python3 scripts/validation/leakage_scan.py || return 1
  else
    pending V3 "CT-56 varredura de vazamento" "script ausente: scripts/validation/leakage_scan.py"
  fi
}

stage_v4() {
  run V4 "npm ci" npm --prefix frontend ci || return 1
  run V4 "npm test" npm --prefix frontend test || return 1
  run V4 "build de producao" npm --prefix frontend run build -- --configuration production || return 1
  # Apenas para registro: o resultado do audit nao reprova a etapa (decisao registrada no relatorio).
  run V4 "npm audit (registro)" bash -c 'npm --prefix frontend audit --omit=dev || true'
}

stage_v5() {
  pending V5 "ponta a ponta (E1 a E11)" "manual, com capturas de tela (docs/qa/validacao-manual-*.md)"
}

stage_v6() {
  run V6 "avaliacao com geracao (metas de qualidade)" bash scripts/eval.sh
}

stage_v7() {
  if [ "$DRY_RUN" -eq 0 ] && [ -z "${NEXUS_ASSISTANT_ID:-}" ]; then
    pending V7 "desempenho" "defina NEXUS_ASSISTANT_ID (assistente de teste) e as credenciais"
    return 0
  fi
  local perf="$OUT/07-desempenho" files="$OUT/corpus"
  run V7 "corpus sintetico" python3 scripts/perf/corpus.py --out "$files" --upload-25mb --index-10mb --count 10 || return 1
  run V7 "RNF-17 upload de 25 MB" python3 scripts/perf/upload_latency.py \
    --base-url "$BASE_URL" --assistant-id "${NEXUS_ASSISTANT_ID:-ID}" --files "$files" --out "$perf/upload.csv" || return 1
  run V7 "RNF-02 tempo de indexacao" python3 scripts/perf/indexing_time.py \
    --base-url "$BASE_URL" --assistant-id "${NEXUS_ASSISTANT_ID:-ID}" --files "$files" --out "$perf/indexacao.csv" || return 1
  run V7 "consolidacao" python3 scripts/perf/report.py \
    "$perf/upload.csv:2:all" "$perf/indexacao.csv:60:all" --out "$OUT/07-desempenho.md"
  pending V7 "RNF-01/03/16/18 (TTFT, busca densa, busca hibrida, reindexacao sob carga)" \
    "ttft.py exige LLM real e perguntas; retrieval_latency.py e reindex_under_load.py ainda nao escritos"
}

stage_v8() {
  run_script V8 "CT-47 backup e restauracao" scripts/validation/backup-restore.sh || return 1
  run_script V8 "CT-48 regressao simulada" scripts/validation/regression-gate.sh || return 1
  run V8 "quality-gate sem regressao" bash scripts/quality-gate.sh
}

for step in "${STEPS[@]}"; do
  selected "$step" || continue
  if ! "stage_$(echo "$step" | tr 'V' 'v')"; then
    echo "Etapa $step falhou: execucao interrompida." >&2
    break
  fi
done

if [ "$DRY_RUN" -eq 1 ]; then exit 0; fi

mkdir -p "$OUT"
{
  echo "# Resultado da validacao ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
  echo
  echo "| Etapa | Item | Resultado |"
  echo "|-------|------|-----------|"
  printf '%s\n' "${SUMMARY[@]}"
} > "$OUT/resumo.md"
cat "$OUT/resumo.md"

if [ "$FAILED" -ne 0 ]; then exit 1; fi
if [ "$PENDING" -ne 0 ]; then echo "Ha itens pendentes: a validacao NAO esta completa." >&2; exit 3; fi
exit 0
