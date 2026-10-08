#!/bin/sh
# Restauracao do Nexus a partir de uma pasta criada por backup.sh
# (SPEC-006: RF-63, cenario "Restauracao"). Feita para ambiente limpo:
# substitui o banco do Nexus e o do Keycloak, as collections e aliases do
# Qdrant presentes no backup e os documentos originais.
#
# Uso, com a API, o worker e o frontend parados:
#   docker compose stop backend worker frontend keycloak
#   docker compose --profile backup run --rm backup restore.sh 20261008T030000Z --yes
#
# Ao final compara as contagens com as gravadas no backup (counts.txt) e
# termina com erro se alguma for diferente.
set -eu
SCRIPT_NAME="restore"
. "$(dirname "$0")/backup-common.sh"

[ "$#" -ge 1 ] || fail "informe a pasta do backup (ex.: 20261008T030000Z)."
source_dir="$1"
case "$source_dir" in
    /*) ;;
    *) source_dir="$BACKUP_ROOT/$source_dir" ;;
esac
[ -d "$source_dir" ] || fail "backup nao encontrado: $source_dir"
[ "${2:-}" = "--yes" ] || fail "a restauracao substitui os dados atuais; repita com --yes."

log "conferindo as somas de verificacao"
(cd "$source_dir" && sha256sum -c -s SHA256SUMS) || fail "arquivo do backup corrompido."

# 1. PostgreSQL.
restore_database() {
    database="$1"
    dump="$2"
    if ! database_exists "$database"; then
        psql -d postgres -c "CREATE DATABASE \"$database\"" > /dev/null
    fi
    pg_restore -d "$database" --clean --if-exists --no-owner --exit-on-error "$dump"
    log "PostgreSQL: $database restaurado"
}
restore_database "$NEXUS_DB" "$source_dir/nexus.dump"
if [ -f "$source_dir/keycloak.dump" ]; then
    restore_database "$KEYCLOAK_DB" "$source_dir/keycloak.dump"
fi

# 2. Qdrant: cada snapshot recria a collection com o mesmo nome.
for snapshot in "$source_dir"/qdrant/*.snapshot; do
    [ -f "$snapshot" ] || continue
    collection=$(basename "$snapshot" .snapshot)
    qdrant POST "/collections/$collection/snapshots/upload?priority=snapshot&wait=true" \
        -F "snapshot=@$snapshot" > /dev/null
    log "Qdrant: $collection restaurada"
done

# Aliases: remove os de mesmo nome e recria como estavam no backup.
existing=$(qdrant GET /aliases | jq -c '[.result.aliases[].alias_name]')
actions=$(jq -c --argjson existing "$existing" '
    [.result.aliases[] | .alias_name as $name
        | (if ($existing | index($name)) then {delete_alias: {alias_name: $name}} else empty end),
          {create_alias: {collection_name: .collection_name, alias_name: $name}}]
' "$source_dir/qdrant/aliases.json")
if [ "$actions" != "[]" ]; then
    qdrant POST /collections/aliases -H 'Content-Type: application/json' \
        -d "{\"actions\": $actions}" > /dev/null
    log "Qdrant: aliases recriados"
fi

# 3. Documentos originais.
if [ -f "$source_dir/documents.tar.gz" ]; then
    mkdir -p "$DOCUMENTS_DIR"
    find "$DOCUMENTS_DIR" -mindepth 1 -delete
    tar -C "$DOCUMENTS_DIR" -xzf "$source_dir/documents.tar.gz"
    log "documentos originais restaurados"
fi

# 4. Conferencia de contagens.
current=$(mktemp)
write_counts > "$current"
if diff -u "$source_dir/counts.txt" "$current"; then
    log "contagens conferem com o backup"
    rm -f "$current"
else
    rm -f "$current"
    fail "contagens diferentes do backup (acima, - backup / + restaurado)."
fi
log "concluido; suba de novo com: docker compose up -d"
