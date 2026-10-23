# Docker

Este diretório deve concentrar Dockerfiles e scripts auxiliares da execução local.

Arquivos previstos:

- `backend.Dockerfile`
- `frontend.Dockerfile`
- `scripts/`

A implementação do ambiente Docker está planejada para a etapa 2 do plano incremental.

## Keycloak (Fase 4)

O `compose.yaml` sobe o serviço `keycloak` (imagem `quay.io/keycloak/keycloak:26.0`, modo de
desenvolvimento) com o realm de `infra/keycloak/nexus-realm.json`. O serviço `keycloak-db-init`
cria antes o banco `keycloak` no PostgreSQL existente. O `frontend.Dockerfile` copia o modelo
`frontend/nginx/default.conf.template`, que o Nginx preenche na subida com os endereços do login.

## Evolução RAG Enterprise (Planejado)

Itens previstos nas especificações e ainda não criados:

- serviço `worker`, usando o mesmo `backend.Dockerfile` com outro comando de entrada;
- volumes `backend_cache` (modelos locais) e `documents_data` (arquivos originais);
- dependências de modelos locais e de OCR no `backend.Dockerfile`;
- perfil opcional de observabilidade.

Detalhes em `docs/infraestrutura/docker-local.md` e `docs/infraestrutura/servicos.md`.
