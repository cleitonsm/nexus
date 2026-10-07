# Docker

Este diretório deve concentrar Dockerfiles e scripts auxiliares da execução local.

Arquivos previstos:

- `backend.Dockerfile`
- `frontend.Dockerfile`
- `scripts/`

A implementação do ambiente Docker está planejada para a etapa 2 do plano incremental.

## Evolução RAG Enterprise (Planejado)

Itens previstos nas especificações e ainda não criados:

- serviço `keycloak` no `compose.yaml` e diretório `infra/keycloak/` com o realm de desenvolvimento;
- serviço `worker`, usando o mesmo `backend.Dockerfile` com outro comando de entrada;
- volumes `backend_cache` (modelos locais) e `documents_data` (arquivos originais);
- dependências de modelos locais e de OCR no `backend.Dockerfile`;
- perfil opcional de observabilidade.

Detalhes em `docs/infraestrutura/docker-local.md` e `docs/infraestrutura/servicos.md`.
