#!/bin/sh
# Backup do Nexus (SPEC-006: RF-63, RNF-28; D5, D10): PostgreSQL do Nexus e do
# Keycloak, snapshot de cada collection do Qdrant (e os aliases) e copia dos
# documentos originais, numa pasta por execucao em BACKUP_PATH.
#
# Uso (o servico "backup" ja roda isto uma vez por dia):
#   docker compose --profile backup run --rm backup backup.sh
#
# Consistencia (D10): a ingestao fica pausada enquanto os tres armazenamentos
# sao copiados, e o backup espera os jobs em andamento. As contagens de
# conferencia (counts.txt) saem do proprio dump, restaurado num banco
# temporario, e do arquivo de documentos, nao da base viva.
#
# A pasta so ganha o nome final quando tudo deu certo; uma execucao
# interrompida deixa "<data>.partial", apagada na execucao seguinte.
set -eu
# pipefail onde o shell suporta (ash do BusyBox e bash; o dash nao tem).
(set -o pipefail) 2>/dev/null && set -o pipefail
SCRIPT_NAME="backup"
. "$(dirname "$0")/backup-common.sh"

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
PAUSE_MAX_SECONDS="${BACKUP_PAUSE_MAX_SECONDS:-3600}"
for value in "$RETENTION_DAYS" "$PAUSE_MAX_SECONDS" "$JOB_TIMEOUT_SECONDS"; do
    case "$value" in
        ''|*[!0-9]*) fail "BACKUP_RETENTION_DAYS, BACKUP_PAUSE_MAX_SECONDS e INGESTION_JOB_TIMEOUT_SECONDS devem ser inteiros." ;;
    esac
done
[ "$RETENTION_DAYS" -ge 1 ] || fail "BACKUP_RETENTION_DAYS deve ser pelo menos 1."

stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_ROOT/$stamp"
partial="$target.partial"
mkdir -p "$partial/qdrant"
log "inicio em $target"

cleanup() {
    resume_ingestion
    psql -d postgres -q -c "DROP DATABASE IF EXISTS $CHECK_DB" > /dev/null 2>&1 || true
}
trap cleanup EXIT

# 1. Pausa (D10): o worker para de reservar jobs; espera os em andamento.
pause_ingestion "$PAUSE_MAX_SECONDS"
log "ingestao pausada; aguardando jobs em andamento"
wait_for_running_jobs || fail "jobs ainda em andamento apos ${JOB_TIMEOUT_SECONDS}s; backup adiado"

# 2. PostgreSQL: formato custom, restauravel com pg_restore --clean.
pg_dump -d "$NEXUS_DB" -Fc -f "$partial/nexus.dump"
if database_exists "$KEYCLOAK_DB"; then
    pg_dump -d "$KEYCLOAK_DB" -Fc -f "$partial/keycloak.dump"
else
    log "banco $KEYCLOAK_DB ausente; seguindo sem ele"
fi
log "PostgreSQL concluido"

# 3. Qdrant: snapshot por collection, baixado e apagado do servidor.
qdrant GET /aliases > "$partial/qdrant/aliases.json"
for collection in $(qdrant GET /collections | jq -r '.result.collections[].name'); do
    snapshot=$(qdrant POST "/collections/$collection/snapshots?wait=true" | jq -r '.result.name')
    [ -n "$snapshot" ] && [ "$snapshot" != "null" ] || fail "snapshot de $collection nao criado"
    qdrant GET "/collections/$collection/snapshots/$snapshot" -o "$partial/qdrant/$collection.snapshot"
    qdrant DELETE "/collections/$collection/snapshots/$snapshot" > /dev/null
    log "Qdrant: $collection"
done
qdrant_counts > "$partial/qdrant-counts.txt"

# 4. Documentos originais (volume documents_data).
if [ -d "$DOCUMENTS_DIR" ]; then
    tar -C "$DOCUMENTS_DIR" -czf "$partial/documents.tar.gz" .
fi

# Copia concluida: a ingestao volta antes da conferencia, que so le o backup.
resume_ingestion
log "ingestao liberada"

# 5. Contagens a partir do backup: o dump e restaurado num banco temporario,
# o que tambem prova que ele e restauravel.
psql -d postgres -q -c "DROP DATABASE IF EXISTS $CHECK_DB" > /dev/null 2>&1
psql -d postgres -q -c "CREATE DATABASE $CHECK_DB" > /dev/null
pg_restore -d "$CHECK_DB" --no-owner --exit-on-error "$partial/nexus.dump"
{
    postgres_counts "$CHECK_DB"
    cat "$partial/qdrant-counts.txt"
    if [ -f "$partial/documents.tar.gz" ]; then
        documents_in_archive "$partial/documents.tar.gz"
    fi
} | sort > "$partial/counts.txt"
rm -f "$partial/qdrant-counts.txt"
psql -d postgres -q -c "DROP DATABASE $CHECK_DB" > /dev/null

{
    printf 'created_at=%s\n' "$stamp"
    printf 'nexus_database=%s\n' "$NEXUS_DB"
    printf 'retention_days=%s\n' "$RETENTION_DAYS"
    printf 'ingestion_paused=true\n'
} > "$partial/manifest.txt"
(cd "$partial" && find . -type f ! -name SHA256SUMS | sort | xargs sha256sum > SHA256SUMS)

mv "$partial" "$target"
log "concluido: $(du -sh "$target" | cut -f1)"

# 6. Retencao: apaga backups completos mais antigos que N dias e restos de
# execucoes interrompidas. O backup recem-criado nunca entra na conta.
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' \
    -mmin +"$((RETENTION_DAYS * 1440))" ! -path "$target" -print \
    | while read -r old; do
        rm -rf "$old"
        log "removido pela retencao: $(basename "$old")"
    done
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '*.partial' \
    ! -path "$partial" -exec rm -rf {} +
