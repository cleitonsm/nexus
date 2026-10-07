# Spec: Autenticação e Controle de Acesso

**ID**: SPEC-20261007-004
**Status**: Rascunho
**Autor**: Cleiton Medeiros (elaborada com apoio de IA generativa, pendente de revisão)
**Data**: 2026-10-07
**Fase**: 4 de 6 — etapa 12 do [plano incremental](../../plano-incremental.md)
**Depende de**: SPEC-20261007-003

## Contexto e Problema

Nenhuma rota da API exige autenticação. Qualquer cliente HTTP com acesso à rede pode listar e
excluir assistentes, enviar documentos, ler conversas de outras pessoas e substituir a chave de
API do LLM. A ADR 0005 aceitou essa limitação apenas para o MVP em rede controlada, e o risco R5
da gestão de riscos definiu como gatilho de mitigação qualquer uso além do ambiente local.

Um RAG corporativo precisa ainda garantir que cada pessoa receba respostas apenas a partir do
conhecimento que pode acessar, e registrar quem consultou o quê.

**Decisão já tomada:** o provedor de identidade é sempre o **Keycloak**, em todos os ambientes.

## Requisitos Funcionais

- [ ] RF-40: autenticação exclusiva pelo Keycloak (OIDC, Authorization Code com PKCE).
- [ ] RF-41: papéis administrador, curador e usuário obtidos do token.
- [ ] RF-42: assistentes vinculados a grupos; visibilidade por grupo.
- [ ] RF-43: restrição de documento por grupo, aplicada na busca.
- [ ] RF-44: conversas privadas de quem as criou.
- [ ] RF-45: trilha de auditoria.
- [ ] RF-46: login, logout e renovação de sessão no frontend.
- [ ] RF-47: administração da chave do LLM restrita ao administrador.

## Requisitos Não Funcionais

- [ ] RNF-22: validação completa do token no backend.
- [ ] RNF-23: restrições aplicadas no servidor, dentro da consulta ao vector store.
- [ ] RNF-24: auditoria somente de inclusão, com retenção configurável.
- [ ] RNF-25: sem tokens ou segredos em logs.
- [ ] RNF-31: migrações versionadas.
- [ ] RNF-32: Keycloak sobe junto com o ambiente, com um único comando.

## Regras de Negócio

- RN-20: nenhum acesso sem autenticação; o Nexus não armazena senhas.
- RN-21: responsabilidades de cada papel.
- RN-22: assistente sem grupo é visível apenas a administradores.
- RN-23: restrição de documento nunca amplia o acesso do assistente.
- RN-24: conteúdo de conversa é privado do criador.
- RN-25: auditoria não pode ser alterada nem excluída.

## Critérios de Aceite (Gherkin)

```gherkin
Funcionalidade: Acesso seguro ao Nexus

  Cenário: Acesso sem autenticação
    Dado que o usuário não possui sessão
    Quando ele acessa qualquer rota do frontend
    Então é redirecionado para a tela de login do Keycloak

  Cenário: API sem token
    Dado uma requisição sem cabeçalho de autorização
    Quando ela chega a qualquer rota exceto "/health"
    Então a resposta é 401
    E nenhum dado é retornado

  Cenário: Token inválido
    Dado um token com assinatura, emissor, audiência ou validade incorretos
    Quando ele é apresentado à API
    Então a resposta é 401

  Cenário: Assistente de outro grupo
    Dado o assistente "RH" vinculado ao grupo "rh"
    E um usuário autenticado que pertence apenas ao grupo "financeiro"
    Quando o usuário lista os assistentes
    Então "RH" não aparece
    Quando o usuário chama diretamente a API de chat do assistente "RH"
    Então a resposta é 403
    E o evento é registrado na auditoria

  Cenário: Assistente sem grupo
    Dado um assistente sem nenhum grupo vinculado
    Quando um usuário sem papel administrador lista os assistentes
    Então o assistente não aparece

  Cenário: Documento restrito
    Dado um documento do assistente restrito ao grupo "diretoria"
    E uma pergunta cuja resposta só existe nesse documento
    Quando um usuário fora do grupo "diretoria" faz a pergunta
    Então nenhum trecho do documento é recuperado
    E o sistema responde com o fallback
    Quando um usuário do grupo "diretoria" faz a mesma pergunta
    Então a resposta cita o documento

  Cenário: Conversa de outro usuário
    Dado uma conversa criada pelo usuário A
    Quando o usuário B solicita essa conversa pelo identificador
    Então a resposta é 404

  Cenário: Configuração do LLM
    Dado um usuário autenticado sem papel administrador
    Quando ele chama as rotas de configuração da chave do LLM
    Então a resposta é 403

  Cenário: Auditoria
    Dado que um usuário fez uma pergunta
    Quando o administrador consulta a auditoria
    Então o evento mostra usuário, assistente, data e documentos recuperados
    E não contém o texto integral dos documentos
```

## Design da Solução

### Keycloak

| Item | Definição |
|------|-----------|
| Serviço | `keycloak` no `compose.yaml`, com banco próprio no PostgreSQL existente (database `keycloak`) |
| Realm | `nexus`, importado na subida a partir de `infra/keycloak/nexus-realm.json` |
| Cliente do frontend | `nexus-frontend`, público, Authorization Code com PKCE |
| Audiência da API | `nexus-api`, incluída no token de acesso por mapeador de audiência |
| Papéis de realm | `nexus-admin`, `nexus-curador`, `nexus-usuario` |
| Grupos | Criados no Keycloak; publicados no token pela claim `groups` |
| Usuários de desenvolvimento | Definidos no realm de exemplo, com dados fictícios |

O realm de exemplo contém apenas dados fictícios e credenciais de desenvolvimento. Segredos de
ambientes reais ficam fora do repositório.

### Backend

| Camada | Componente | Responsabilidade |
|--------|------------|------------------|
| Domínio | `AuthenticatedUser` (id, nome, papéis, grupos) | Identidade usada pelos casos de uso |
| Domínio | `AccessPolicy` | Regras RN-21 a RN-24, sem dependência de framework |
| Domínio | `TokenVerifier` (Protocol) | Validar token e devolver `AuthenticatedUser` |
| Domínio | `AssistantPermissionRepository`, `AuditLogRepository` (Protocol) | Persistência de vínculos e de eventos |
| Aplicação | Casos de uso existentes | Passam a receber o `AuthenticatedUser` e consultar a `AccessPolicy` |
| Aplicação | `SetAssistantGroupsUseCase`, `SetDocumentGroupsUseCase`, `ListAuditEventsUseCase` | Novos casos de uso |
| Infraestrutura | `KeycloakTokenVerifier` | Validação por JWKS, com cache das chaves públicas |
| Infraestrutura | Repositórios PostgreSQL de permissões e de auditoria | Persistência |
| API | Dependência `get_current_user` e verificação de papel | Aplicada a todos os routers, exceto `/health` |

A regra de acesso fica no domínio (`AccessPolicy`); as rotas apenas traduzem HTTP e os casos de
uso decidem. O domínio continua sem importar FastAPI ou bibliotecas de JWT.

### Autorização na busca

- Cada chunk recebe o campo de payload `allowed_groups`: lista de grupos autorizados, ou vazio
  quando o documento segue o acesso do assistente.
- Um índice de payload é criado sobre `allowed_groups`.
- `hybrid_search` recebe os grupos do usuário e aplica o filtro: `allowed_groups` vazio **ou**
  interseção com os grupos do usuário.
- O acesso ao assistente é verificado antes da busca; o filtro de documento só restringe (RN-23).
- Alterar a restrição de um documento atualiza o payload dos seus chunks, sem reindexar vetores.

A collection por assistente (ADR 0003) é mantida: ela garante o isolamento entre assistentes, e o
filtro de payload acrescenta a restrição dentro do assistente.

### Modelo de dados

| Tabela | Alteração |
|--------|-----------|
| `assistant_groups` | Nova: `assistant_id`, `group_name` |
| `document_groups` | Nova: `document_id`, `group_name` |
| `conversations` | Nova coluna `owner_user_id` |
| `audit_events` | Nova: `id`, `occurred_at`, `user_id`, `action`, `resource_type`, `resource_id`, `details` (JSON), sem operações de alteração ou exclusão |

Migração dos dados existentes: assistentes do MVP ficam sem grupo, portanto visíveis apenas a
administradores até serem vinculados (RN-22); conversas anteriores ficam sem dono e não são
exibidas a usuários comuns.

### API

| Rota | Papel | Descrição |
|------|-------|-----------|
| Todas as existentes | Conforme RN-21 | Passam a exigir token |
| `GET /me` | Qualquer autenticado | Identidade, papéis e grupos do usuário |
| `PUT /assistants/{id}/groups` | Administrador | Define os grupos do assistente |
| `PUT /documents/{id}/groups` | Curador com acesso, administrador | Define a restrição do documento |
| `GET /admin/audit-events` | Administrador | Consulta a auditoria, com filtros |
| `/admin/api-key/*` | Administrador | Rotas existentes, agora restritas |

### Frontend

- Fluxo OIDC com PKCE; tokens mantidos em memória, com renovação silenciosa.
- Interceptor HTTP anexa o token e trata 401 e 403.
- Guards de rota por papel; itens de menu ocultos conforme o papel.
- Estado NgRx de sessão (`auth`): usuário, papéis, grupos e situação da sessão.
- Telas novas: permissões do assistente, restrição de documento e consulta de auditoria.
- O Nginx passa a encaminhar apenas o necessário; CORS do backend restrito à origem do frontend.

### Novas variáveis

`KEYCLOAK_URL`, `KEYCLOAK_REALM`, `OIDC_AUDIENCE`, `OIDC_FRONTEND_CLIENT_ID`,
`KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`, `AUDIT_RETENTION_DAYS`, `CORS_ALLOWED_ORIGINS`.

## Impacto Arquitetural

- Domínio: identidade, política de acesso e três novas portas.
- Aplicação: todos os casos de uso passam a receber o usuário autenticado.
- Infraestrutura: verificador de token, repositórios novos, filtro de payload no Qdrant.
- Docker: novo serviço `keycloak`; novo diretório `infra/keycloak/`.
- Documentação: C4 de contexto e de containers ganham o Keycloak.
- ADRs: [0008 — Keycloak e modelo de permissões](../../arquitetura/adrs/0008-keycloak-e-modelo-de-permissoes.md),
  que complementa a 0003 e encerra a limitação registrada na 0005.

## Estratégia de Testes

- Unitários: CT-23, CT-24, CT-25, CT-32.
- Integração: CT-26, CT-27, CT-28, CT-29, CT-30, CT-31, com Keycloak em container.
- Os testes unitários usam um `TokenVerifier` dublê; nenhum teste unitário depende do Keycloak.

## Riscos e Dependências

- Falha na aplicação do filtro de acesso expõe conteúdo entre grupos (risco R12): é o risco de
  maior impacto da evolução e tem testes recorrentes.
- Complexidade operacional do Keycloak e bloqueio de login se ele estiver indisponível (risco R13).
- Migração dos dados existentes pode ocultar assistentes e conversas até a configuração de grupos (risco R20).
- O Keycloak aumenta o uso de memória do ambiente local (risco R17).

## Decisões Pendentes

| Decisão | Opções | Impacto |
|---------|--------|---------|
| Restrição por documento nesta fase | Entregar junto; entregar apenas acesso por assistente e adiar RF-43 | RF-43 representa parte relevante do esforço da fase |
| Conversas anteriores à autenticação | Atribuir a um administrador; arquivar; excluir | Preservação do histórico do MVP |
| Acesso de administradores ao conteúdo de conversas | Manter privado (RN-24); permitir com registro em auditoria | Privacidade e capacidade de suporte |
| Versão do Keycloak e origem dos usuários | Usuários locais no realm; federação com diretório corporativo | Operação e integração com a empresa |
