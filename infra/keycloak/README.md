# Keycloak — realm de desenvolvimento

`nexus-realm.json` é importado na primeira subida do serviço `keycloak` (`start-dev
--import-realm`). **Contém apenas dados fictícios e credenciais de desenvolvimento**; não use este
arquivo fora do ambiente local. Segredos de ambientes reais ficam fora do repositório.

## O que o realm define

| Item | Valor |
|------|-------|
| Realm | `nexus` |
| Cliente do frontend | `nexus-frontend`, público, Authorization Code com PKCE (S256) |
| Cliente de testes `nexus-tests` | Público, só *direct access grants*, com os mesmos mapeadores de audiência e grupos do frontend. Serve ao CT-52, ao CT-56 e às medições (`scripts/perf`); existe apenas no realm de desenvolvimento (V-D2) e deve ser removido de qualquer realm exposto |
| Cliente de serviço do backend | `nexus-backend`, confidencial, só *client credentials*; a conta de serviço tem os papéis `query-groups` e `view-users` do `realm-management`, só leitura, para listar os grupos na tela e validá-los no envio (PC-D6; SPEC-009 D5: sem `view-users` o Keycloak devolve a lista vazia, e todo grupo é recusado com 422). Segredo `${NEXUS_BACKEND_CLIENT_SECRET}`, vindo de `KEYCLOAK_BACKEND_CLIENT_SECRET` |
| Audiência da API | `nexus-api`, incluída no token de acesso pelo mapeador `audiencia-nexus-api` |
| Papéis de realm | `nexus-admin`, `nexus-curador`, `nexus-usuario` |
| Grupos | `rh`, `financeiro`, `diretoria`, publicados na claim `groups` (sem o caminho) |
| Eventos de login | Ligados, guardados por 12 meses no próprio Keycloak |

## Usuários de exemplo

Todos com a senha `nexus-dev`.

| Usuário | Papel | Grupos |
|---------|-------|--------|
| `admin.nexus` | `nexus-admin` | — |
| `curadora.rh` | `nexus-curador` | `rh` |
| `usuario.rh` | `nexus-usuario` | `rh` |
| `usuario.financeiro` | `nexus-usuario` | `financeiro` |
| `diretora` | `nexus-usuario` | `rh`, `diretoria` |

O console de administração fica em `http://localhost:8080/admin`, com o usuário e a senha de
`KEYCLOAK_ADMIN` e `KEYCLOAK_ADMIN_PASSWORD` (padrão `admin` / `admin`).

## Alterar o realm

A importação só acontece quando o realm ainda não existe. Depois da primeira subida, mudanças
neste arquivo não são aplicadas: altere pelo console de administração ou recrie o banco
`keycloak` (`DROP DATABASE keycloak;` no PostgreSQL, com o serviço `keycloak` parado) e suba de
novo.

O endereço do frontend não fica fixo no arquivo: `redirectUris`, `webOrigins`, `rootUrl` e
`post.logout.redirect.uris` do cliente `nexus-frontend` usam `${NEXUS_FRONTEND_URL}`, que o
Keycloak resolve pelo ambiente na importação (decisão PC-D1 do
[plano de conclusão](../../docs/plano-de-conclusao.md)). O Compose passa a variável ao serviço
`keycloak`, com o padrão `http://localhost:4200`. Para servir o frontend em outro endereço:

1. defina `NEXUS_FRONTEND_URL` no `.env` (por exemplo `http://nexus.local:8081`) e inclua o mesmo
   valor em `CORS_ALLOWED_ORIGINS`;
2. se o realm já foi importado, recrie o banco `keycloak` como descrito acima, ou ajuste o
   cliente pelo console, porque a importação não sobrescreve um realm existente.

O mesmo vale para o cliente `nexus-backend` (PC-D6): num realm importado antes de 2026-10-08 ele
não existe, e a tela de assistentes usa o campo de texto para os grupos. Para ativá-lo sem
recriar o banco, crie no console um cliente confidencial `nexus-backend` só com *Service accounts
roles*, dê à conta de serviço os papéis `query-groups` e `view-users` do cliente `realm-management` e use o segredo
gerado em `KEYCLOAK_BACKEND_CLIENT_SECRET`. Fora do ambiente local, troque o segredo padrão.

Num realm importado antes de 2026-10-20 a conta só tem `query-groups`. Para incluir `view-users` sem recriar o
banco (PowerShell, credenciais de administrador do `.env`, padrão `admin`/`admin`):

```powershell
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080 --realm master --user admin --password admin
docker compose exec keycloak /opt/keycloak/bin/kcadm.sh add-roles -r nexus --uusername service-account-nexus-backend --cclientid realm-management --rolename view-users
docker compose restart backend worker   # descarta a lista vazia guardada por 60 s
```
