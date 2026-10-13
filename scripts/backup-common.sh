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
# Tempo limite de um job do worker (SPEC-005 D7); tambem a espera maxima do backup.
JOB_TIMEOUT_SECONDS="${INGESTION_JOB_TIMEOUT_SECONDS:-600}"
# Banco temporario onde o dump e conferido antes de gerar as contagens.
CHECK_DB="nexus_backup_check"

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

# --- Pausa da ingestao (SPEC-006 D10) -------------------------------------
# O worker le a chave "ingestion_pause" de app_settings antes de reservar
# jobs (PostgresIngestionPauseRepository). O SQL e o mesmo do teste
# tests/integration/test_ingestion_pause_storage.py.
pause_ingestion() {
    seconds="$1"
    psql -d "$NEXUS_DB" -v ON_ERROR_STOP=1 -q -c "
        INSERT INTO app_settings (key_name, value, updated_by, updated_at)
        VALUES ('ingestion_pause',
                json_build_object('paused_until', now() + make_interval(secs => $seconds),
                                  'reason', 'backup'),
                'backup', now())
        ON CONFLICT (key_name) DO UPDATE
        SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by, updated_at = now()"
}

resume_ingestion() {
    psql -d "$NEXUS_DB" -q -c "DELETE FROM app_settings WHERE key_name = 'ingestion_pause'" \
        || log "AVISO: pausa nao liberada; ela expira sozinha no prazo gravado"
}

# Jobs que o worker ainda esta executando: ingestao reservada ha menos que o
# tempo limite (D7) e reindexacao com reserva vigente (PC-D4).
running_jobs() {
    psql -d "$NEXUS_DB" -tAc "
        SELECT (SELECT count(*) FROM ingestion_jobs
                WHERE status = 'processando'
                  AND reserved_at > now() - make_interval(secs => $JOB_TIMEOUT_SECONDS))
             + (SELECT count(*) FROM reindex_jobs
                WHERE status = 'running' AND lease_expires_at > now())"
}

wait_for_running_jobs() {
    waited=0
    while [ "$(running_jobs)" != "0" ]; do
        [ "$waited" -lt "$JOB_TIMEOUT_SECONDS" ] || return 1
        sleep 5
        waited=$((waited + 5))
    done
}

# --- Contagens de conferencia ----------------------------------------------
# Uma linha "chave=valor" por tabela, collection e arquivos. Sem conteudo.
postgres_counts() {
    database="$1"
    for table in $COUNTED_TABLES; do
        value=$(psql -d "$database" -tAc "SELECT count(*) FROM $table" 2>/dev/null || echo "ausente")
        printf 'postgres.%s=%s\n' "$table" "$value"
    done
}

qdrant_counts() {
    for collection in $(qdrant GET /collections | jq -r '.result.collections[].name'); do
        value=$(qdrant POST "/collections/$collection/points/count" \
            -H 'Content-Type: application/json' -d '{"exact": true}' | jq -r '.result.count')
        printf 'qdrant.%s=%s\n' "$collection" "$value"
    done
}

documents_in_dir() {
    printf 'documents.files=%s\n' "$(find "$1" -type f | wc -l | tr -d ' ')"
}

documents_in_archive() {
    printf 'documents.files=%s\n' "$(tar -tzf "$1" | grep -vc '/$' || true)"
}

# Contagens da base viva, usadas depois da restauracao.
write_counts() {
    {
        postgres_counts "$NEXUS_DB"
        qdrant_counts
        if [ -d "$DOCUMENTS_DIR" ]; then
            documents_in_dir "$DOCUMENTS_DIR"
        fi
    } | sort
}
