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

## Evolução RAG Enterprise (Planejado)

Funcionalidades especificadas em `docs/especificacao/specs/` e ainda não implementadas:

- login, logout e renovação de sessão pelo Keycloak (OIDC com PKCE);
- rotas e menus condicionados ao papel (administrador, curador, usuário);
- fontes exibidas em cada resposta, com o trecho citado;
- resposta em streaming e avaliação da resposta (útil / não útil);
- gestão de documentos com estado de ingestão, exclusão, substituição e restrição por grupo;
- telas administrativas de permissões, auditoria e consumo.

A organização do estado e dos serviços está em `docs/arquitetura/frontend-angular-ngrx.md`.
