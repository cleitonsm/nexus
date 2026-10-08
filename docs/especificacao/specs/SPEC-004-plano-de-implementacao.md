# Plano de Implementação — SPEC-004 Autenticação e Controle de Acesso

**Spec**: [SPEC-20261007-004](SPEC-004-autenticacao-e-controle-de-acesso.md) (Aprovada em 2026-10-07)
**Status do plano**: Código de P1 a P8 entregue em 2026-10-07; decisões D6 a D8 aplicadas em 2026-10-08; a validação no Docker está pendente
**Data**: 2026-10-07
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## 0. Andamento

| Pacote | Situação em 2026-10-07 | Verificado por |
|--------|------------------------|----------------|
| P1 Domínio | Entregue: `AuthenticatedUser`, `Role`, `AccessPolicy`, `AuditEvent`, `AuditQuery`, portas `TokenVerifier`, `AssistantPermissionRepository` e `AuditLogRepository`, dono em `Conversation`, `allowed_groups` em `VectorChunk`, `user_groups` obrigatório em `hybrid_search` | Testes unitários (CT-24, CT-25) |
| P2 Aplicação | Entregue: `AccessControl` e `AuditTrail`; todos os casos de uso de rota recebem o usuário; novos `SetAssistantGroupsUseCase`, `SetDocumentGroupsUseCase`, `ListDocumentsUseCase`, `ListAuditEventsUseCase`, `DeleteAssistantUseCase`, `GetConversationUseCase`, `DeleteConversationUseCase`, `AddMessageUseCase`, `DescribeCurrentUserUseCase` | Testes unitários |
| P3 Verificador de token | Entregue: `KeycloakTokenVerifier` (RS256 por JWKS, emissor, audiência, validade), com cache das chaves | Testes unitários (CT-23), com chave RSA gerada no teste |
| P4 Persistência | Código entregue: migração `0004_access_control`, modelos, `PostgresAssistantPermissionRepository`, `PostgresAuditLogRepository`, gatilho que recusa UPDATE, DELETE e TRUNCATE em `audit_events` | Nada: SQLAlchemy e Alembic não estavam disponíveis fora do Docker |
| P5 Qdrant | Código entregue: payload `allowed_groups`, índice de payload, filtro de acesso nas duas pré-buscas e na busca densa de base antiga, `set_document_groups` | Nada: `qdrant-client` não estava disponível fora do Docker |
| P6 API | Código entregue: `get_current_user` em todos os routers, 403 por `AccessDeniedError`, `GET /me`, `PUT /assistants/{id}/groups`, `GET /assistants/{id}/documents`, `PUT /documents/{id}/groups`, `GET /admin/audit-events`, CORS restrito, documentação interativa só com `APP_ENV=local` | Nada: FastAPI não estava disponível |
| P7 Docker e Keycloak | Entregue: serviços `keycloak` e `keycloak-db-init`, realm `infra/keycloak/nexus-realm.json`, `/config.json` no Nginx, variáveis novas | Sintaxe do `compose.yaml` e do realm; lógica do healthcheck testada contra um servidor HTTP local. O Keycloak não foi executado |
| P8 Frontend | Código entregue: PKCE e cliente OIDC sem biblioteca, `AuthService` (tokens em memória, renovação silenciosa), interceptor, guards por papel, estado NgRx `auth`, menu por papel, telas de permissões, restrição de documento e auditoria | Lógica sem Angular (PKCE, cliente OIDC, decisão do guard, menu) e reducers: 55 testes rodados com um substituto local do Vitest e do NgRx. Componentes, templates, interceptor e guard: só sintaxe; sem build |
| P9 Validação no Docker | Não iniciado | — |

Verificação feita: **372 testes unitários do backend passam** (265 anteriores, todos adaptados para
receber o usuário, e 107 novos), fora do Docker, em Python 3.13, com o LangGraph substituído por um
dublê local. Uma verificação estática não encontrou nomes indefinidos, imports sem uso nem
definições duplicadas em `backend/src` e `backend/tests`.

**Não verificado**: migração, repositórios, adaptador Qdrant, rotas, CORS, todos os testes de
integração (os novos e os das Fases 2 e 3), o Keycloak (importação do realm, conteúdo do token,
healthcheck dentro da imagem), a construção das imagens e o frontend montado (build do Angular,
templates e fluxo de login no navegador). As Fases 2 e 3 também não foram validadas no Docker:
a primeira execução vai revelar ajustes das três fases juntas.

## 0.1 Como validar no Docker

1. Copiar para o `.env`, se ele sobrescrever valores, as variáveis novas do `.env.example`
   (bloco "Autenticação"). Sem isso valem os padrões do `.env.example`.
2. `docker compose up -d --build`. A subida cria o banco `keycloak`, importa o realm `nexus` e
   aplica a migração `0004_access_control`. O Keycloak leva cerca de um minuto na primeira vez.
3. Abrir `http://localhost:4200`: o navegador deve ir ao login do Keycloak. Entrar com
   `admin.nexus` / `nexus-dev` (demais usuários em [`infra/keycloak/README.md`](../../../infra/keycloak/README.md)).
4. **Se a tela "Não foi possível entrar no Nexus" aparecer** com a mensagem de token recusado,
   decodificar o token de acesso (aba Rede do navegador, chamada a `/api/me`) e conferir:
   `iss` igual a `KEYCLOAK_URL/realms/nexus`, `aud` contendo `nexus-api`, `sub` presente,
   `realm_access.roles` e `groups`. O log do backend registra o motivo em `auth.token.rejected`.
5. **Vincular grupos aos assistentes que já existiam**: como administrador, em "Documentos e
   permissões". Até lá eles só aparecem para administradores (RN-22, risco R20). As conversas
   anteriores ficam arquivadas e não aparecem para ninguém.
6. Testes no container:
   `docker compose run --rm --no-deps -v ./backend/tests:/app/tests backend python -m unittest discover -s tests/unit`
   e o mesmo com `-s tests/integration` (sem `--no-deps`). Os testes de auditoria gravam eventos
   de teste (usuários `teste-...`) que só a limpeza por retenção remove.
   Limpeza por retenção: `docker compose run --rm backend python -m src.cli.purge_audit`.
7. Frontend: `npm ci && npm test && npm run build` em `frontend/`.
8. Validação manual dos cenários da spec: usuário de outro grupo não vê o assistente; documento
   restrito a `diretoria` leva ao fallback para `usuario.rh` e é citado para `diretora`; conversa
   de outra pessoa responde 404; "Configurações" e "Auditoria" só aparecem para o administrador;
   a auditoria mostra a pergunta com os documentos recuperados.

## 1. Decisões

Registradas por Cleiton Medeiros em 2026-10-07.

| # | Decisão | Escolha |
|---|---------|---------|
| D1 | Aprovação da SPEC-004 e da ADR 0008 | Aprovadas pelo pedido de implementação, sobre as Fases 2 e 3 ainda não validadas no Docker |
| D2 | Restrição por documento (RF-43) | Entregue nesta fase |
| D3 | Conversas anteriores à autenticação | Arquivadas: ficam no banco sem dono e fora das listas dos usuários. Alterada pela PC-D5 (2026-10-08): o administrador lista, lê e exclui, com auditoria (`archived_conversation.*`) |
| D4 | Acesso de administradores a conversas | Mantido privado (RN-24): conversa alheia responde 404 também para o administrador |
| D5 | Origem dos usuários | Usuários locais no realm de exemplo; federação com diretório fica para depois |

Tomadas por Cleiton Medeiros em 2026-10-08, depois da entrega do código:

| # | Decisão | Escolha | Efeito no código |
|---|---------|---------|------------------|
| D6 | Retenção da auditoria (RNF-24 x RN-25) | Comando de manutenção | `python -m src.cli.purge_audit` apaga os eventos mais antigos que `AUDIT_RETENTION_DAYS` (padrão 365) e registra a limpeza (`audit.purged`, usuário `system:maintenance`). O gatilho só aceita DELETE na transação que liga `nexus.audit_purge` com `SET LOCAL`; UPDATE e TRUNCATE continuam recusados. A API não oferece a operação |
| D7 | Versão do Keycloak | Mantida `26.0` | Nenhum |
| D8 | Restrição já no envio | Grupos no envio | Campo `groups` (lista JSON) no `POST /assistants/{id}/documents`; os trechos já são gravados restritos e a resposta devolve os grupos. Campo "Restringir os novos arquivos" na tela de documentos |

## 2. Comportamentos definidos na implementação

A spec não fixava estes pontos. Em 2026-10-08 o autor revisou C1, C5, C7, C9 e C13: C9 foi
alterado e os demais mantidos. Os outros seguem como implementados e podem ser alterados.

| # | Comportamento | Como ficou |
|---|---------------|------------|
| C1 | Validação do token sem biblioteca de JWT | **Mantido pelo autor.** A assinatura RS256 é conferida com `cryptography`, que o projeto já usa, para não acrescentar dependência. Só RS256 é aceito |
| C2 | Tolerância de relógio | Nenhuma: token expirado no mesmo segundo é recusado |
| C3 | Chaves do Keycloak | Guardadas por 5 minutos; chave desconhecida provoca nova consulta, no máximo uma a cada 10 segundos. Se o Keycloak não responder e já houver chaves, elas continuam valendo; sem nenhuma chave, o token é recusado |
| C4 | Token sem papel do Nexus | Autentica, mas não acessa assistente nem rota administrativa; `GET /me` responde |
| C5 | Restrição de documento e administrador | **Mantido pelo autor.** A restrição vale também para o administrador que não pertence ao grupo (leitura literal da RN-23). Ele vê e altera a restrição, mas o chat dele não recupera o documento |
| C6 | Grupos do documento fora dos grupos do assistente | Aceitos. Não ampliam nada: o acesso ao assistente é verificado antes da busca |
| C7 | Texto da pergunta na auditoria | **Mantido pelo autor.** Não é gravado, por causa da D4: a auditoria mostra usuário, assistente, conversa, documentos recuperados e citados, e se houve fallback |
| C8 | Evento de autenticação | `auth.session_started` é gravado quando o frontend chama `GET /me`, uma vez por abertura da página. O login em si é registrado pelo Keycloak. Token recusado vai só para o log (`auth.token.rejected`) |
| C9 | Pergunta que falha | **Alterado pelo autor.** A pergunta interrompida por erro também entra na auditoria: `chat.question` com `failed: true`, o tipo do erro e os documentos já recuperados; a resposta continua com erro. As respondidas levam `failed: false` |
| C10 | Falha ao gravar a auditoria | Propaga o erro: a operação responde 500 |
| C11 | Reindexação em curso | `PUT /documents/{id}/groups` responde 409, como o upload: a collection em construção já copiou a restrição anterior |
| C12 | Falha do Qdrant ao regravar a restrição | O banco volta à restrição anterior e a rota responde erro |
| C13 | Conversa de assistente a que o usuário perdeu acesso | **Mantido pelo autor.** O dono ainda lê e exclui a conversa; perguntar responde 403 |
| C14 | Avaliação por linha de comando | Age como `system:evaluation`, com papel de administrador, e busca sem restrição por documento; as ações dela aparecem na auditoria com esse identificador |
| C15 | Documentação interativa da API | `/docs`, `/redoc` e `/openapi.json` só existem com `APP_ENV=local` e ficam fora do proxy do Nginx, porque não exigem token |
| C16 | Sessão no frontend | Tokens só em memória. Recarregar a página passa de novo pelo Keycloak, que reconhece a sessão e volta sem pedir senha. O `state`, o verificador do PKCE e o endereço de retorno ficam no `sessionStorage` apenas durante a ida ao login |
| C17 | Erro no login | O frontend não redireciona de novo sozinho; mostra a mensagem e um botão "Tentar novamente", para não entrar em laço se a configuração estiver errada |
| C18 | Rotas novas fora da tabela da spec | `GET /assistants/{id}/documents`, necessária para a tela de restrição, e o campo `groups` na resposta de assistentes, preenchido só para quem gerencia o assistente |
| C19 | Variável fora da lista da spec | `KEYCLOAK_INTERNAL_URL`: o navegador chega ao Keycloak por `localhost` e a API, pelo nome do serviço; o emissor conferido é o de `KEYCLOAK_URL` |
| C20 | Paginação da auditoria | 50 eventos por consulta, no máximo 200; o frontend mostra a primeira página |

## 3. Pacotes

### P1 — Domínio (RN-20 a RN-25)

`domain/access.py` e `domain/audit.py`, sem dependência de framework. `AccessPolicy` nega por
padrão. `hybrid_search` e `ContextRetriever.search` passam a exigir `user_groups` como argumento
nomeado sem valor padrão: esquecer o filtro é um erro de execução, não uma busca sem filtro
(risco R12).

### P2 — Aplicação

`AccessControl` é o único ponto em que os casos de uso consultam a política; toda negação grava
`access.denied` e levanta `AccessDeniedError`. As rotas que tinham regra própria (excluir
assistente, ler, excluir e acrescentar mensagem em conversa) passaram a casos de uso.
`RunReindexUseCase` roda sem usuário e grava em cada trecho a restrição vigente do documento.

### P3 — Verificador de token (RNF-22)

`infrastructure/auth/keycloak_token_verifier.py`. Recusa: assinatura de outra chave, conteúdo
alterado, emissor, audiência, expiração, `nbf` futuro, token sem `sub`, algoritmo `none` ou
simétrico, token malformado e `kid` desconhecido.

### P4 — Persistência (RNF-31)

Migração `0004_access_control`: `assistant_groups`, `document_groups`,
`conversations.owner_user_id` e `audit_events`. Reversível. Nenhum dado existente é alterado.

### P5 — Qdrant (RF-43, RNF-23)

Filtro `allowed_groups` vazio **ou** com algum grupo do usuário, aplicado em cada pré-busca.
Trechos gravados antes desta fase não têm o campo e continuam sem restrição, por isso **não é
preciso reindexar** e `PIPELINE_VERSION` continua `3`.

### P6 — API

Cada router declara `dependencies=[Depends(get_current_user)]`: uma rota nova no router já nasce
exigindo token. O CT-26 percorre todas as rotas da aplicação.

### P7 — Docker e Keycloak (RNF-32)

`keycloak-db-init` cria o banco `keycloak` se não existir, também em volumes anteriores à fase.
O backend depende do Keycloak apenas iniciado: as chaves são buscadas na primeira requisição com
token.

### P8 — Frontend (RF-46)

Sem biblioteca nova: PKCE com o Web Crypto do navegador. O Nginx publica `/config.json` com os
endereços do login, lidos do ambiente na subida do container.

## 4. Testes

| Caso | Situação | Onde |
|------|----------|------|
| CT-23 | Implementado e executado | `backend/tests/unit/test_token_verifier.py` |
| CT-24, CT-25 | Implementados e executados | `backend/tests/unit/test_access_control.py` |
| CT-26, CT-27, CT-29, CT-30 | Implementados, ainda não executados (exigem FastAPI); os contratos equivalentes, com dublês, rodam em `test_access_control.py` | `backend/tests/integration/test_access_control_api.py` |
| CT-28 | Implementado, ainda não executado (exige o Qdrant) | `backend/tests/integration/test_access_control_storage.py` |
| CT-31 | Implementado, ainda não executado (exige o PostgreSQL) | `backend/tests/integration/test_access_control_storage.py` e `test_access_control_api.py` |
| CT-32 | Implementado; a lógica foi executada com um substituto local do Vitest, e a execução com o Vitest real está pendente | `frontend/src/app/core/auth/access.spec.ts` e `frontend/src/app/store/auth.reducer.spec.ts` |

Diferença em relação à spec: os testes de integração **não sobem o Keycloak**. O CT-30 usa o
verificador real com tokens assinados por uma chave gerada no teste, o que confere a leitura dos
papéis do token sem depender do serviço. O login pelo Keycloak de verdade fica na validação manual.

## 5. Lacunas conhecidas

- A SPEC-004 pede migração de dados "explícita" para assistentes e conversas: nada é migrado, e
  o efeito (assistentes ocultos, conversas arquivadas) precisa ser comunicado antes de ativar a
  fase em um ambiente com dados (risco R20).
- Conversas arquivadas: tela do administrador desde 2026-10-08 (PC-D5); não há como atribuí-las a
  um usuário.
- Os grupos são digitados como texto; o Nexus não consulta o Keycloak para listar os grupos
  existentes, então um nome digitado errado não é detectado.
- O realm de exemplo só aceita o frontend em `http://localhost:4200`.
- Corrigido de passagem, por estar na rota reescrita: `POST /admin/api-key/test` passava um texto
  onde o LLM espera a lista de trechos e respondia 500.
- Não corrigidos, anteriores a esta fase: o envio de vários arquivos de uma vez cancela os
  anteriores (`switchMap` no efeito de upload); os blocos `#region agent log` do frontend
  continuam enviando dados de depuração a `http://127.0.0.1:7657`; `.env.example` usa
  `UPLOAD_MAX_BYTES` e `DOCUMENTS_STORAGE_PATH`, que o código não lê.
- A skill `desenvolvedor-nexus` ainda descreve o MVP (hash, busca densa, rotas sem autenticação).
