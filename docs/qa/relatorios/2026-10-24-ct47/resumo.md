# CT-47 — backup, ambiente limpo e restauração

Data: 2026-10-24T19:49:51-03:00. Projeto principal: nexus. Ambiente limpo: nexus-ct47.

| Etapa | Resultado | Detalhe |
|---|---|---|
| Backup | OK | pasta 20261024T224952Z (01-backup.log) |
| Ambiente limpo | OK | PostgreSQL e Qdrant vazios (03-ambiente-limpo.log) |
| Restauração e contagens | OK | restore.sh compara com counts.txt (04-restauracao.log) |
| Consistência PostgreSQL x Qdrant | OK | check_consistency (05-consistencia.log) |
| Busca nos dados restaurados | OK | restored_search (06-busca.json) |

Resultado: 0 falha(s). Commit 1bfc1fe.
