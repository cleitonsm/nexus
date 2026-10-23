#!/usr/bin/env bash
# Ensaio rapido de scripts/backup.sh e restore.sh (SPEC-006 D10), sem Docker:
# PostgreSQL real (o do CI ou um local) e Qdrant simulado (fake_qdrant.py).
# Complementa o CT-47, que roda no Docker com os servicos reais.
#
# Confere: a pausa existe durante o backup e e liberada no fim; o backup espera
# um job em andamento; as contagens do backup batem com a restauracao numa base
# vazia; a base restaurada nao herda a pausa; um backup corrompido e recusado.
#
# Requer psql, pg_dump, pg_restore, curl, jq, python3 e as variaveis PGHOST,
# PGPORT, PGUSER e PGPASSWORD de um usuario que crie bancos.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
QDRANT_SOURCE_PORT=56333
QDRANT_CLEAN_PORT=56334
export QDRANT_API_KEY="chave-ficticia"
export POSTGRES_USER="$PGUSER" POSTGRES_PASSWORD="$PGPASSWORD"
export BACKUP_PGHOST="$PGHOST" BACKUP_DIR="$WORK/backups"
export INGESTION_JOB_TIMEOUT_SECONDS=30 BACKUP_PAUSE_MAX_SECONDS=600

pids=()
cleanup() {
    for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done
    rm -rf "$WORK"
}
trap cleanup EXIT

# assert "descricao" comando...: o comando precisa terminar com sucesso.
assert() {
    local description="$1"
    shift
    if "$@"; then echo "[OK] $description"; else echo "[FALHA] $description"; exit 1; fi
}
refuses() {
    local description="$1"
    shift
    if "$@" > /dev/null 2>&1; then echo "[FALHA] $description"; exit 1; fi
    echo "[OK] $description"
}
sql() { psql -X -q -tA -v ON_ERROR_STOP=1 -d "$1" -c "SET client_min_messages = warning" -c "$2"; }

# Ambiente de origem: banco com dados ficticios, arquivos e Qdrant com pontos.
for db in nexus_ensaio keycloak nexus_restaurado; do
    sql postgres "DROP DATABASE IF EXISTS $db"
done
sql postgres "CREATE DATABASE nexus_ensaio"
sql postgres "CREATE DATABASE keycloak"
psql -X -q -v ON_ERROR_STOP=1 -d nexus_ensaio -f "$ROOT/scripts/validation/backup-fixture.sql"
mkdir -p "$WORK/docs/a1" "$WORK/docs-limpo" "$BACKUP_DIR"
echo "conteudo ficticio 1" > "$WORK/docs/a1/d1.pdf"
echo "conteudo ficticio 2" > "$WORK/docs/d2.md"
python3 "$ROOT/scripts/validation/fake_qdrant.py" "$QDRANT_SOURCE_PORT" \
    '{"assistant_a1_v1": 120, "assistant_a2_v2": 45}' & pids+=($!)
python3 "$ROOT/scripts/validation/fake_qdrant.py" "$QDRANT_CLEAN_PORT" & pids+=($!)
sleep 1

# Backup com um job em andamento que termina 7 s depois.
sql nexus_ensaio "INSERT INTO ingestion_jobs VALUES ('j1', 'processando', now())"
( sleep 7; sql nexus_ensaio "UPDATE ingestion_jobs SET status = 'concluido' WHERE id = 'j1'" ) &
finisher=$!
( sleep 3; sql nexus_ensaio "SELECT count(*) FROM app_settings WHERE key_name = 'ingestion_pause'" \
    > "$WORK/pausa-durante.txt" ) &
observer=$!
started=$(date +%s)
assert "backup concluido" env POSTGRES_DB=nexus_ensaio BACKUP_DOCUMENTS_DIR="$WORK/docs" \
    BACKUP_QDRANT_URL="http://127.0.0.1:$QDRANT_SOURCE_PORT" \
    sh "$ROOT/scripts/backup.sh"
wait "$finisher" "$observer"
assert "ingestao pausada durante o backup" [ "$(cat "$WORK/pausa-durante.txt")" = "1" ]
assert "backup esperou o job em andamento" [ $(( $(date +%s) - started )) -ge 7 ]
assert "pausa liberada no fim" \
    [ "$(sql nexus_ensaio "SELECT count(*) FROM app_settings WHERE key_name = 'ingestion_pause'")" = "0" ]

# Restauracao numa base vazia, com conferencia de contagens.
stamp=$(ls "$BACKUP_DIR" | grep -E 'Z$' | tail -1)
assert "restauracao com contagens iguais as do backup" env POSTGRES_DB=nexus_restaurado \
    BACKUP_KEYCLOAK_DB=keycloak_restaurado BACKUP_DOCUMENTS_DIR="$WORK/docs-limpo" \
    BACKUP_QDRANT_URL="http://127.0.0.1:$QDRANT_CLEAN_PORT" \
    sh "$ROOT/scripts/restore.sh" "$stamp" --yes
assert "base restaurada sem a pausa do backup" \
    [ "$(sql nexus_restaurado "SELECT count(*) FROM app_settings WHERE key_name = 'ingestion_pause'")" = "0" ]

# Backup corrompido e recusado.
cp -r "$BACKUP_DIR/$stamp" "$BACKUP_DIR/corrompido"
echo x >> "$BACKUP_DIR/corrompido/nexus.dump"
refuses "backup corrompido recusado" env POSTGRES_DB=nexus_restaurado \
    BACKUP_QDRANT_URL="http://127.0.0.1:$QDRANT_CLEAN_PORT" \
    sh "$ROOT/scripts/restore.sh" corrompido --yes

for db in nexus_ensaio keycloak nexus_restaurado keycloak_restaurado; do
    sql postgres "DROP DATABASE IF EXISTS $db"
done
echo "Ensaio dos scripts de backup concluido."
