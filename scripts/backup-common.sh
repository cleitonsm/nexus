# Funcoes comuns de backup.sh e restore.sh (SPEC-006, RF-63). POSIX sh.
# Executados no servico "backup" do Compose (infra/docker/backup.Dockerfile).

BACKUP_ROOT="${BACKUP_DIR:-/backups}"
DOCUMENTS_DIR="${BACKUP_DOCUMENTS_DIR:-/documents}"
PGHOST="${BACKUP_PGHOST:-postgres}"
QDRANT_URL_BASE="${BACKUP_QDRANT_URL:-http://qdrant:6333}"
KEYCLOAK_DB="${BACKUP_KEYCLOAK_DB:-keycloak}"
export PGHOST
export PGUSER="${POSTGRES_USER:?POSTGRES_USER nao definido}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD nao definido}"
NEXUS_DB="${POSTGRES_DB:?POSTGRES_DB nao definido}"

# Tabelas conferidas depois da restauracao. Sem conteudo: so contagens.
COUNTED_TABLES="assistants documents conversations messages assistant_groups document_groups audit_events usage_records message_feedback"

log() {
    printf '%s %s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SCRIPT_NAME" "$*"
}

fail() {
    log "ERRO: $*" >&2
    exit 1
}

# curl no Qdrant com a chave da API; a chave nunca vai para o log.
qdrant() {
    method="$1"
    path="$2"
    shift 2
    curl -fsS -X "$method" -H "api-key: ${QDRANT_API_KEY:-}" "$@" "$QDRANT_URL_BASE$path"
}

database_exists() {
    psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$1'" | grep -q 1
}

# Uma linha "chave=valor" por tabela e por collection, ordenadas.
write_counts() {
    {
        for table in $COUNTED_TABLES; do
            value=$(psql -d "$NEXUS_DB" -tAc "SELECT count(*) FROM $table" 2>/dev/null || echo "ausente")
            printf 'postgres.%s=%s\n' "$table" "$value"
        done
        for collection in $(qdrant GET /collections | jq -r '.result.collections[].name'); do
            value=$(qdrant POST "/collections/$collection/points/count" \
                -H 'Content-Type: application/json' -d '{"exact": true}' | jq -r '.result.count')
            printf 'qdrant.%s=%s\n' "$collection" "$value"
        done
        if [ -d "$DOCUMENTS_DIR" ]; then
            printf 'documents.files=%s\n' "$(find "$DOCUMENTS_DIR" -type f | wc -l | tr -d ' ')"
        fi
    } | sort
}
