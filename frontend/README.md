# Frontend Nexus

Frontend Angular com Tailwind e NgRx para o MVP:

- cadastro e seleção de assistentes;
- upload de documentos por assistente;
- chat com renderização Markdown e destaque de código;
- estado previsível com store/effects/selectors.

## Comandos

- `npm install`
- `npm start`
- `npm run build`

No ambiente Docker, o Nginx faz proxy de `/api/*` para o serviço `backend`.

## Autenticação (Fase 4)

- Login pelo Keycloak com Authorization Code e PKCE, sem biblioteca: `src/app/core/auth`.
- Os tokens ficam apenas em memória e são renovados antes de expirar. Recarregar a página passa
  de novo pelo Keycloak, que reconhece a sessão aberta.
- O interceptor anexa o token às chamadas de `/api/`; 401 volta ao login e 403 vira mensagem.
- Guards por papel nas rotas e menu conforme o papel (estado NgRx `auth`).
- Telas: "Documentos e permissões" (`/assistants`), "Auditoria" (`/admin/audit`).
- Os endereços do login vêm de `/config.json`: no Docker, o Nginx o gera a partir de
  `KEYCLOAK_URL`, `KEYCLOAK_REALM` e `OIDC_FRONTEND_CLIENT_ID`; com `npm start`, vale
  `public/config.json`.
- O frontend esconde o que o papel não pode usar, mas quem autoriza é a API.

## Evolução RAG Enterprise (Planejado)

Funcionalidades especificadas em `docs/especificacao/specs/` e ainda não implementadas:

- resposta em streaming e avaliação da resposta (útil / não útil);
- gestão de documentos com estado de ingestão, exclusão e substituição;
- tela administrativa de consumo.

A organização do estado e dos serviços está em `docs/arquitetura/frontend-angular-ngrx.md`.
