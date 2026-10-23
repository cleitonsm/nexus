#!/usr/bin/env bash
# CT-47 (SPEC-006: RF-63, RNF-28; decisao D11): backup do ambiente atual,
# restauracao num ambiente limpo, conferencia de contagens e uma busca.
#
# Pre-requisito: o ambiente principal no ar (docker compose up -d) com pelo
# menos um documento indexado. Nada nele e alterado alem da pausa de ingestao
# durante o backup (D10).
#
# O ambiente limpo e outro projeto do Compose (nexus-ct47), com volumes
# proprios e portas deslocadas; as imagens do ambiente principal sao
# reaproveitadas e o cache dos modelos locais e montado do ambiente principal.
#
# Uso (na raiz do repositorio, Linux, macOS ou Git Bash):
#   scripts/validation/backup-restore.sh            # executa e apaga o ambiente limpo
#   scripts/validation/backup-restore.sh --keep     # mantem o ambiente limpo para inspecao
#
# Evidencias em docs/qa/relatorios/<data>-ct47/. Codigo de saida 0 so se todas
# as etapas passarem.
set -uo pipefail

cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1

KEEP=0
[ "${1:-}" = "--keep" ] && KEEP=1

MAIN_PROJECT="${COMPOSE_PROJECT_NAME:-$(basename "$PWD" | tr '[:upper:]' '[:lower:]')}"
CLEAN_PROJECT="nexus-ct47"
BACKUP_HOST_DIR="${BACKUP_PATH:-./backups}"
OUT="docs/qa/relatorios/$(date +%Y-%m-%d)-ct47"
mkdir -p "$OUT"
SUMMARY="$OUT/resumo.md"
FAILURES=0

main_compose() { docker compose -p "$MAIN_PROJECT" "$@"; }
# Portas deslocadas: o ambiente limpo convive com o principal.
clean_compose() {
    POSTGRES_PORT=55432 QDRANT_PORT=56333 BACKEND_PORT=58000 \
        docker compose -p "$CLEAN_PROJECT" "$@"
}

record() {
    local step="$1" ok="$2" detail="$3"
    local mark="OK"
    if [ "$ok" != "0" ]; then
        mark="FALHA"
        FAILURES=$((FAILURES + 1))
    fi
    printf '| %s | %s | %s |\n' "$step" "$mark" "$detail" >> "$SUMMARY"
    printf '[%s] %s - %s\n' "$mark" "$step" "$detail"
}

finish() {
    if [ "$KEEP" -eq 0 ]; then
        clean_compose --profile backup down -v > "$OUT/09-limpeza.log" 2>&1
    fi
    printf '\nResultado: %s falha(s). Commit %s.\n' "$FAILURES" \
        "$(git rev-parse --short HEAD 2>/dev/null || echo desconhecido)" >> "$SUMMARY"
    echo "Evidencias em $OUT"
    [ "$FAILURES" -eq 0 ]
}

{
    echo "# CT-47 — backup, ambiente limpo e restauração"
    echo
    echo "Data: $(date -Iseconds). Projeto principal: $MAIN_PROJECT. Ambiente limpo: $CLEAN_PROJECT."
    echo
    echo "| Etapa | Resultado | Detalhe |"
    echo "|---|---|---|"
} > "$SUMMARY"

# 1. Backup do ambiente principal ----------------------------------------------
main_compose --profile backup run --rm backup backup.sh > "$OUT/01-backup.log" 2>&1
status=$?
STAMP=$(ls -1 "$BACKUP_HOST_DIR" 2>/dev/null | grep -E '^20[0-9]{6}T[0-9]{6}Z$' | sort | tail -1)
record "Backup" "$status" "pasta ${STAMP:-nenhuma} (01-backup.log)"
if [ "$status" -ne 0 ] || [ -z "$STAMP" ]; then
    finish
    exit 1
fi
cp "$BACKUP_HOST_DIR/$STAMP/counts.txt" "$OUT/02-contagens-do-backup.txt"

# 2. Ambiente limpo -------------------------------------------------------------
for image in backend backup; do
    docker tag "$MAIN_PROJECT-$image" "$CLEAN_PROJECT-$image" > /dev/null 2>&1
done
clean_compose --profile backup down -v > /dev/null 2>&1
clean_compose up -d --wait postgres qdrant > "$OUT/03-ambiente-limpo.log" 2>&1
record "Ambiente limpo" "$?" "PostgreSQL e Qdrant vazios (03-ambiente-limpo.log)"

# 3. Restauracao com conferencia de contagens ----------------------------------
clean_compose --profile backup run --rm backup restore.sh "$STAMP" --yes \
    > "$OUT/04-restauracao.log" 2>&1
record "Restauração e contagens" "$?" "restore.sh compara com counts.txt (04-restauracao.log)"

# 4. Conferencia PostgreSQL x Qdrant (R18) e uma busca -------------------------
run_backend() {
    clean_compose run --rm --no-deps \
        -v "${MAIN_PROJECT}_backend_cache:/app/cache" \
        -v "./backend/tests:/app/tests:ro" \
        backend "$@"
}
run_backend python -m src.cli.check_consistency > "$OUT/05-consistencia.log" 2>&1
record "Consistência PostgreSQL x Qdrant" "$?" "check_consistency (05-consistencia.log)"
run_backend python -m tests.validation.restored_search > "$OUT/06-busca.json" 2> "$OUT/06-busca.log"
record "Busca nos dados restaurados" "$?" "restored_search (06-busca.json)"

finish
