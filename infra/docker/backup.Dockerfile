# Servico "backup" (SPEC-006 D5): pg_dump da mesma versao do servidor
# (PostgreSQL 16) curl e jq para os snapshots do Qdrant.
FROM postgres:16-alpine

RUN apk add --no-cache curl jq tar

COPY scripts/backup-common.sh scripts/backup.sh scripts/restore.sh scripts/backup-loop.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh /usr/local/bin/backup-loop.sh

ENTRYPOINT []
CMD ["backup-loop.sh"]
