# Keycloak — realm de desenvolvimento

`nexus-realm.json` é importado na primeira subida do serviço `keycloak` (`start-dev
--import-realm`). **Contém apenas dados fictícios e credenciais de desenvolvimento**; não use este
arquivo fora do ambiente local. Segredos de ambientes reais ficam fora do repositório.

## O que o realm define

| Item | Valor |
|------|-------|
| Realm | `nexus` |
| Cliente do frontend | `nexus-frontend`, público, Authorization Code com PKCE (S256) |
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

Se o frontend passar a ser servido em outro endereço, ajuste `redirectUris`, `webOrigins` e
`post.logout.redirect.uris` do cliente `nexus-frontend`, e `CORS_ALLOWED_ORIGINS` no backend.
