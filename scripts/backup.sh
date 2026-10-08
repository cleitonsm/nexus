#!/bin/sh
# Backup do Nexus (SPEC-006: RF-63, RNF-28; D5): PostgreSQL do Nexus e do
# Keycloak, snapshot de cada collection do Qdrant (e os aliases) e copia dos
# documentos originais, numa pasta por execucao em BACKUP_PATH.
#
# Uso (o servico "backup" ja roda isto uma vez por dia):
#   docker compose --profile backup run --rm backup backup.sh
#
# A pasta so ganha o nome final quando tudo deu certo; uma execucao
# interrompida deixa "<data>.partial", apagada na execucao seguinte.
set -eu
SCRIPT_NAME="backup"
. "$(dirname "$0")/backup-common.sh"

RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
case "$RETENTION_DAYS" in
    ''|*[!0-9]*) fail "BACKUP_RETENTION_DAYS deve ser um numero inteiro de dias." ;;
esac
[ "$RETENTION_DAYS" -ge 1 ] || fail "BACKUP_RETENTION_DAYS deve ser pelo menos 1."

stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="$BACKUP_ROOT/$stamp"
partial="$target.partial"
mkdir -p "$partial/qdrant"
log "inicio em $target"

# 1. PostgreSQL: formato custom, restauravel com pg_restore --clean.
pg_dump -d "$NEXUS_DB" -Fc -f "$partial/nexus.dump"
if database_exists "$KEYCLOAK_DB"; then
    pg_dump -d "$KEYCLOAK_DB" -Fc -f "$partial/keycloak.dump"
else
    log "banco $KEYCLOAK_DB ausente; seguindo sem ele"
fi
log "PostgreSQL concluido"

# 2. Qdrant: snapshot por collection, baixado e apagado do servidor.
qdrant GET /aliases > "$partial/qdrant/aliases.json"
for collection in $(qdrant GET /collections | jq -r '.result.collections[].name'); do
    snapshot=$(qdrant POST "/collections/$collection/snapshots?wait=true" | jq -r '.result.name')
    [ -n "$snapshot" ] && [ "$snapshot" != "null" ] || fail "snapshot de $collection nao criado"
    qdrant GET "/collections/$collection/snapshots/$snapshot" -o "$partial/qdrant/$collection.snapshot"
    qdrant DELETE "/collections/$collection/snapshots/$snapshot" > /dev/null
    log "Qdrant: $collection"
done

# 3. Documentos originais (volume documents_data).
if [ -d "$DOCUMENTS_DIR" ]; then
    tar -C "$DOCUMENTS_DIR" -czf "$partial/documents.tar.gz" .
fi

# 4. Contagens para a conferencia da restauracao e somas de verificacao.
write_counts > "$partial/counts.txt"
{
    printf 'created_at=%s\n' "$stamp"
    printf 'nexus_database=%s\n' "$NEXUS_DB"
    printf 'retention_days=%s\n' "$RETENTION_DAYS"
} > "$partial/manifest.txt"
(cd "$partial" && find . -type f ! -name SHA256SUMS | sort | xargs sha256sum > SHA256SUMS)

mv "$partial" "$target"
log "concluido: $(du -sh "$target" | cut -f1)"

# 5. Retencao: apaga backups completos mais antigos que N dias e restos de
# execucoes interrompidas. O backup recem-criado nunca entra na conta.
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '20*Z' \
    -mmin +"$((RETENTION_DAYS * 1440))" ! -path "$target" -print \
    | while read -r old; do
        rm -rf "$old"
        log "removido pela retencao: $(basename "$old")"
    done
find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '*.partial' \
    ! -path "$partial" -exec rm -rf {} +
