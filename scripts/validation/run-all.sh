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
# ou NEXUS_TOKEN, NEXUS_PERF_CHUNKS (padrao 100000) e NEXUS_PERF_WAIT_MINUTES (espera
# da fila antes da RNF-02, padrao 90). V5 (ponta a ponta) e manual: o script registra como pendente.
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
# Conjunto da V6 (secao 6.1 do plano de validacao: cerca de 80 itens validados).
EVAL_DATASET="${NEXUS_EVAL_DATASET:-nexus-docs-ampliado}"
# Modelo oficial da V6 (PC-D8); a V6 reprova relatorio gerado com outro modelo.
export EVAL_MODEL="${NEXUS_EVAL_MODEL:-gemini-3.8-flash}"
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

# run_strict <etapa> <descricao> <comando...>: como run, mas reprova se o unittest
# pulou algum teste ("skipped" nao e aprovacao: o motivo precisa ser resolvido).
run_strict() {
  local step="$1" label="$2"; shift 2
  # A saida vai para o log enquanto roda (tee); a copia serve para procurar pulos.
  run "$step" "$label" bash -c '
    copy=$(mktemp)
    "$@" 2>&1 | tee "$copy"; rc=${PIPESTATUS[0]}
    skipped=0; grep -qE "skipped=[1-9]" "$copy" && skipped=1
    rm -f "$copy"
    [ "$rc" -eq 0 ] || exit "$rc"
    if [ "$skipped" -eq 1 ]; then
      echo "REPROVADO: ha testes pulados; resolva o motivo antes de aprovar a etapa"
      exit 1
    fi' _ "$@"
}

# Pasta de relatorio vista pelo docker compose (relativa a raiz, como os outros volumes).
case "$OUT" in
  /*|[A-Za-z]:*) OUT_MOUNT="$OUT" ;;
  *) OUT_MOUNT="./$OUT" ;;
esac

# Comando no container do backend com as montagens usadas na rodada de integracao
# (docs/qa/relatorios/2026-10-16-rodada-integracao): testes, avaliacao, scripts e relatorio.
BACKEND_RUN=(docker compose run --rm -e PYTHONPATH=/app:/app/integration
  -v ./backend/tests:/app/tests
  -v ./backend/tests/integration:/app/integration:ro
  -v ./backend/tests/evaluation:/app/evaluation
  -v ./scripts:/app/scripts:ro
  -v "$OUT_MOUNT:/app/out"
  backend)

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
  # So o codigo da aplicacao; os *.spec.ts usam o nome em dubles do DomSanitizer.
  run V0 "varredura de bypassSecurityTrustHtml" \
    bash -c '! git grep -n "bypassSecurityTrustHtml" -- frontend/src ":(exclude)*.spec.ts"' || return 1
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
  # /app e a pasta backend do repositorio; os testes que leem scripts/ e docs/ procuram a
  # raiz do repositorio um nivel acima (/), onde as duas pastas sao montadas.
  run V2 "testes unitarios no container" docker compose run --rm --no-deps \
    -v ./backend/tests:/app/tests -v ./scripts:/scripts:ro -v ./docs:/docs:ro \
    backend python -m unittest discover -s tests/unit -v
}

stage_v3() {
  # Sem pulos: CT-40 exige /app/scripts; CT-55 usa http://frontend (rede do Compose).
  run_strict V3 "testes de integracao do backend" "${BACKEND_RUN[@]}" \
    sh -c 'cd /app/tests/integration && python -m unittest discover -s . -v' || return 1
  run_script V3 "CT-53 resiliencia do worker" scripts/validation/worker_resilience.sh || return 1
  run_script V3 "CT-54 operacao offline" scripts/validation/offline_check.sh || return 1
  if [ -f scripts/validation/leakage_scan.py ] || [ "$DRY_RUN" -eq 1 ]; then
    run V3 "CT-56 varredura de vazamento" "${BACKEND_RUN[@]}" \
      python /app/scripts/validation/leakage_scan.py --out /app/out/ct56 || return 1
  else
    pending V3 "CT-56 varredura de vazamento" "script ausente: scripts/validation/leakage_scan.py"
  fi
}

# npm do host ou, sem ele (o caso do Windows deste projeto), o container node:22, como na
# rodada de 2026-10-16. NEXUS_NPM=docker forca o container.
npm_frontend() {
  if [ "${NEXUS_NPM:-}" != "docker" ] && command -v npm >/dev/null 2>&1; then
    npm --prefix frontend "$@"
  else
    local dir="$PWD/frontend"
    command -v cygpath >/dev/null 2>&1 && dir="$(cygpath -w "$dir")"
    "${NEXUS_DOCKER:-docker}" run --rm -v "$dir:/app" -w /app node:22 npm "$@"
  fi
}

npm_audit_record() { npm_frontend audit --omit=dev || true; }

stage_v4() {
  run V4 "npm ci" npm_frontend ci || return 1
  run V4 "npm test" npm_frontend test || return 1
  run V4 "build de producao" npm_frontend run build -- --configuration production || return 1
  # Apenas para registro: o resultado do audit nao reprova a etapa (decisao registrada no relatorio).
  run V4 "npm audit (registro)" npm_audit_record
}

stage_v5() {
  pending V5 "ponta a ponta (E1 a E11)" "manual, com capturas de tela (docs/qa/validacao-manual-*.md)"
}

stage_v6() {
  # V-D5: 3 execucoes completas com geracao. Sem a chave do LLM (o down -v da V0 apaga a
  # cadastrada na tela) a avaliacao pularia a geracao so com um aviso: cada execucao confere.
  # O verificador roda no container do backend (o Windows do autor nao precisa de Python).
  local reports="/app/evaluation/reports/$EVAL_DATASET" n
  for n in 1 2 3; do
    run V6 "avaliacao $n de 3 ($EVAL_DATASET)" bash -c \
      'scripts/eval.sh "$1" && shift && "$@" --runs 1 --only-generation --model "$EVAL_MODEL"' \
      _ "$EVAL_DATASET" "${BACKEND_RUN[@]}" python /app/scripts/validation/check_eval_reports.py "$reports" || return 1
  done
  run V6 "metas da secao 6.3 (recall, fidelidade, fallback, citacoes)" \
    "${BACKEND_RUN[@]}" python /app/scripts/validation/check_eval_reports.py "$reports" --runs 3 --model "$EVAL_MODEL"
}

stage_v7() {
  # Tudo no container do backend, na rede do Compose: o Windows do autor nao precisa de Python,
  # a API e http://backend:8000 e o Keycloak e http://keycloak:8080 (o emissor do token continua
  # sendo o KC_HOSTNAME). Usuario de teste: cliente nexus-tests do realm de desenvolvimento.
  local perf="$OUT/07-desempenho" perfc="/app/out/07-desempenho" files="/app/out/corpus"
  local chunks="${NEXUS_PERF_CHUNKS:-100000}" api="http://backend:8000" assistant
  local run_perf=(docker compose run --rm -e PYTHONPATH=/app:/app/integration
    -e NEXUS_TEST_USER="${NEXUS_TEST_USER:-admin.nexus}"
    -e NEXUS_TEST_PASSWORD="${NEXUS_TEST_PASSWORD:-nexus-dev}"
    -e KEYCLOAK_URL="${NEXUS_KEYCLOAK_INTERNAL_URL:-http://keycloak:8080}"
    -v ./scripts:/app/scripts:ro -v "$OUT_MOUNT:/app/out" backend)
  run V7 "assistente de desempenho" "${run_perf[@]}" python /app/scripts/perf/ensure_assistant.py \
    --base-url "$api" --out "$perfc/assistant-id.txt" --fresh || return 1
  if [ "$DRY_RUN" -eq 1 ]; then assistant="ID"; else assistant="$(tr -d '\r\n' < "$perf/assistant-id.txt")"; fi
  run V7 "corpus sintetico (arquivos)" "${run_perf[@]}" python /app/scripts/perf/corpus.py \
    --out "$files" --upload-25mb --index-10mb --count 10 || return 1
  # RNF-17 com o worker pausado (decisao do autor, 2026-10-22): mede a resposta da API sem a
  # disputa de CPU com a indexacao dos arquivos anteriores. A indexacao e medida na RNF-02,
  # depois que a fila acumulada esvaziar (senao a RNF-02 conta a espera pela fila).
  local upload_ok=0
  run V7 "pausa do worker (RNF-17)" docker compose stop worker || return 1
  run V7 "RNF-17 upload de 25 MB" "${run_perf[@]}" python /app/scripts/perf/upload_latency.py \
    --base-url "$api" --assistant-id "$assistant" --files "$files" --out "$perfc/upload.csv" || upload_ok=1
  # Os arquivos de 25 MB so medem a resposta do upload: saem antes de o worker voltar.
  run V7 "documentos da RNF-17 apagados" "${run_perf[@]}" python /app/scripts/perf/purge_documents.py \
    --base-url "$api" --assistant-id "$assistant" || upload_ok=1
  run V7 "retomada do worker" docker compose up -d --wait worker || return 1
  [ "$upload_ok" -eq 0 ] || return 1
  run V7 "fila vazia antes da RNF-02" "${run_perf[@]}" python /app/scripts/perf/wait_idle.py \
    --base-url "$api" --assistant-id "$assistant" --wait-minutes "${NEXUS_PERF_WAIT_MINUTES:-90}" || return 1
  run V7 "RNF-02 tempo de indexacao" "${run_perf[@]}" python /app/scripts/perf/indexing_time.py \
    --base-url "$api" --assistant-id "$assistant" --files "$files" --out "$perfc/indexacao.csv" || return 1
  # RNF-03 e RNF-16: 100.000 trechos sinteticos (PC-D9) gravados direto na collection perf-load.
  run V7 "corpus de $chunks trechos" "${run_perf[@]}" python /app/scripts/perf/corpus.py \
    --out "$files" --chunks "$chunks" || return 1
  run V7 "carga dos trechos (perf-load)" "${run_perf[@]}" \
    python /app/scripts/perf/retrieval_latency.py load --chunks "$files/chunks.jsonl" --replace || return 1
  run V7 "RNF-03 busca densa" "${run_perf[@]}" \
    python /app/scripts/perf/retrieval_latency.py dense --chunks "$files/chunks.jsonl" --out "$perfc/rnf03.csv" || return 1
  run V7 "RNF-16 busca hibrida, 1 usuario" "${run_perf[@]}" \
    python /app/scripts/perf/retrieval_latency.py hybrid --chunks "$files/chunks.jsonl" --users 1 --out "$perfc/rnf16-u1.csv" || return 1
  run V7 "RNF-16 busca hibrida, 5 usuarios" "${run_perf[@]}" \
    python /app/scripts/perf/retrieval_latency.py hybrid --chunks "$files/chunks.jsonl" --users 5 --out "$perfc/rnf16-u5.csv" || return 1
  # RNF-18: a reindexacao rele os documentos do banco, entao usa o assistente cuja base foi
  # enviada pela API nos passos acima (os 100.000 trechos da perf-load nao tem documentos).
  run V7 "RNF-18 busca durante a reindexacao" "${run_perf[@]}" \
    python /app/scripts/perf/reindex_under_load.py --base-url "$api" --assistant-id "${NEXUS_REINDEX_ASSISTANT_ID:-$assistant}" \
    --chunks "$files/chunks.jsonl" --users 1 --out "$perfc/rnf18.csv" || return 1
  # RNF-01 (decisao do autor, 2026-10-22): LLM real, sobre o assistente que a V6 indexa, com as
  # perguntas do escopo do conjunto validado; 100 perguntas, 5 simultaneas (secao 7 do plano).
  local ttft_assistant="Nexus Docs (avaliacao)"
  [ "$EVAL_DATASET" = "nexus-docs-ampliado" ] && ttft_assistant="Nexus Docs Ampliado (avaliacao)"
  # Mesmo comando do run_perf (o ultimo item e o servico), com o conjunto montado.
  local run_ttft=("${run_perf[@]:0:${#run_perf[@]}-1}" -v ./backend/tests/evaluation/datasets:/app/datasets:ro backend)
  run V7 "RNF-01 TTFT (LLM real)" "${run_ttft[@]}" \
    python /app/scripts/perf/ttft.py --base-url "$api" --assistant-name "$ttft_assistant" \
    --dataset "/app/datasets/$EVAL_DATASET.jsonl" --samples 100 --concurrency 5 --out "$perfc/ttft.csv" || return 1
  run V7 "consolidacao" "${run_perf[@]}" python /app/scripts/perf/report.py \
    "$perfc/ttft.csv:30:p95" "$perfc/upload.csv:2:all" "$perfc/indexacao.csv:60:all:PC-D11" \
    "$perfc/rnf03.csv:2:all" "$perfc/rnf16-u1.csv:3:p95" "$perfc/rnf16-u5.csv" "$perfc/rnf18.csv" \
    --out "/app/out/07-desempenho.md"
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
