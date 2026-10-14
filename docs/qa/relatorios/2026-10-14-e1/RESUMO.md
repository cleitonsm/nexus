# Teste rapido no Docker (E1) - 2026-10-14

Commit `4584080`; subida ate saudavel em 145 s; falhas automaticas: 3.

| Etapa | Resultado | Detalhe |
|-------|-----------|---------|
| Ambiente | OK   | commit 4584080 |
| docker compose up | OK   | codigo 0 (ver 01-up.log) |
| Servicos saudaveis | OK   | 145 s ate saudavel; backend=running/healthy, worker=running/, frontend=running/healthy, postgres=running/healthy, qdrant=running/healthy, keycloak=running/healthy |
| alembic current (head) | OK   | 0007_reindex_in_worker (head) |
| requirements x pip freeze | FALHA | divergencias: psycopg[binary]==3.2.7 |
| API /health | OK   | HTTP 200 (esperado 200) |
| API /assistants sem token | OK   | HTTP 401 (esperado 401) |
| Frontend /health | OK   | HTTP 200 (esperado 200) |
| Nginx /api/metrics bloqueado | OK   | HTTP 404 (esperado 404) |
| Keycloak realm nexus | OK   | HTTP 200 (esperado 200) |
| Erros nos logs | FALHA |  ocorrencias de Traceback/ERROR |
| Aviso de versao do Qdrant | FALHA | worker-1    | 2026-10-14T13:51:31.860552575Z /usr/local/lib/python3.12/site-packages/qdrant_client/qdrant_remote.py:284: UserWarning: Qdrant client version 1.19.1 is incompatible with server version 1.11.3. Major versions should match and minor version difference must not exceed 1. Set check_compatibility=False to skip version check. / backend-1   | 2026-10-14T13:51:24.218119340Z /usr/local/lib/python3.12/site-packages/qdrant_client/qdrant_remote.py:284: UserWarning: Qdrant client version 1.19.1 is incompatible with server version 1.11.3. Major versions should match and minor version difference must not exceed 1. Set check_compatibility=False to skip version check. |
