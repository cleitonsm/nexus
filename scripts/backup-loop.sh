#!/bin/sh
# Agenda do servico "backup" (SPEC-006 D5): uma execucao ao subir e depois a
# cada BACKUP_INTERVAL_SECONDS (padrao: 24 h, ponto de recuperacao do RNF-28).
# Uma falha e registrada no log e a proxima tentativa acontece em 1 hora.
set -u
INTERVAL="${BACKUP_INTERVAL_SECONDS:-86400}"
RETRY_SECONDS=3600

while true; do
    if backup.sh; then
        sleep "$INTERVAL"
    else
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) backup falhou; nova tentativa em ${RETRY_SECONDS}s" >&2
        sleep "$RETRY_SECONDS"
    fi
done
