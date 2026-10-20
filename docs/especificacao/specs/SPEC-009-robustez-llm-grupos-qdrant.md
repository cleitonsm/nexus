# SPEC-009 — Robustez do LLM, grupos de documentos e versão do cliente Qdrant

**ID**: SPEC-20261014-009
**Status**: Aprovada em 2026-10-14 (decisões D1 a D4 escolhidas pelo autor); código entregue, validação no Docker pendente
**Origem**: teste rápido no Docker (E1): 503 passageiro do Google ao testar o LLM; documento enviado com o grupo literal "Sem restrição" que ficou invisível a todos; aviso de incompatibilidade `qdrant-client` 1.19.1 × servidor 1.11.3
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## Contexto e problema

1. Uma falha passageira do provedor (503 "high demand", 429, queda de conexão) derruba a pergunta do
   usuário na primeira tentativa, mesmo que a segunda funcionasse.
2. O envio de documentos aceita qualquer texto como grupo. Um grupo que não existe no Keycloak
   restringe o documento a ninguém: as buscas devolvem 0 candidatos e o chat só responde o fallback,
   sem nenhum aviso.
3. O cliente `qdrant-client` 1.19.1 está fora da janela de compatibilidade do servidor 1.11.3 (a
   biblioteca exige a mesma versão maior e no máximo uma menor de diferença).

## Decisões

| # | Escolha |
|---|---------|
| D1 | O cliente é fixado em `qdrant-client==1.11.3`, a mesma série do servidor (`qdrant/qdrant:v1.11.3`). O servidor e os índices existentes não mudam. |
| D2 | Nova tentativa no LLM: 3 tentativas no total, com espera de 1 s e de 3 s. Repete só em HTTP 429, 500, 502, 503, 504 e em falha de conexão; nunca em 400, 401, 403 ou 404. Não repete depois que o provedor começou a responder (o fluxo de streaming só abre depois dos cabeçalhos, então nenhum trecho é duplicado). Tempo esgotado na leitura da resposta não repete, para não triplicar a espera nem cobrar duas vezes. Valores fixos no código, sem variável de ambiente nova. |
| D3 | Grupos informados ao enviar um documento ou ao restringi-lo (RF-43) precisam existir na lista de grupos do Keycloak; grupo desconhecido responde 422 com os nomes recusados e nada é gravado. Se a lista estiver indisponível (Keycloak fora do ar ou cliente de serviço ausente, 503 em `/groups`), o envio é aceito sem validar e o fato é registrado em log. Lista vazia (remover a restrição) nunca consulta o Keycloak. A comparação usa o nome normalizado (sem espaços e sem a barra inicial), exato quanto a maiúsculas e minúsculas, como o filtro de acesso. |
| D4 | A fila de curadoria continua só com avaliações "não útil" (RN-33); nenhuma mudança em feedback. |
| D5 | (2026-10-20, decidida pelo autor) A conta de serviço `nexus-backend` recebe também o papel `view-users` do `realm-management`. Achado do CT-56 na V3: com só `query-groups`, o Keycloak 26 responde `GET /admin/realms/nexus/groups` com 200 e lista vazia (só lista os grupos que quem pergunta pode ver), e o D3 recusava todo grupo com 422 — nenhum documento restrito podia ser enviado. Os testes anteriores usavam dublês do diretório. `view-users` é só leitura (usuários e grupos); alternativas descartadas: permissões finas por grupo (complexas no realm de desenvolvimento) e lista fixa no `.env` (diverge do Keycloak). Teste com o Keycloak real: `test_keycloak_real.GroupDirectoryRealTests`. Realms já importados recebem o papel pelo comando do `infra/keycloak/README.md`. |

Fora do escopo: grupos dos assistentes (RF-42, só administrador) continuam sem validação; ficam
registrados como evolução possível.

## Requisitos funcionais

- RF-73: chamadas ao LLM (teste da chave, pergunta com e sem streaming, avaliação) repetem a requisição
  conforme D2; o usuário só vê o erro depois da última tentativa, com a mesma mensagem de hoje.
- RF-74: envio de documento e alteração dos grupos de um documento recusam grupos que não existem no
  Keycloak, conforme D3.

## Critérios de aceite

```gherkin
Cenário: falha passageira do provedor (RF-73)
  Dado que o provedor responde 503 na primeira tentativa e 200 na segunda
  Quando o usuário pergunta
  Então a resposta é entregue e o log registra uma nova tentativa

Cenário: erro que não adianta repetir (RF-73)
  Dado que o provedor responde 401
  Quando o administrador testa a chave
  Então há uma única chamada e o erro é devolvido na hora

Cenário: provedor fora do ar (RF-73)
  Dado que o provedor responde 503 nas três tentativas
  Quando o usuário pergunta
  Então o erro de comunicação com o LLM é devolvido depois da terceira

Cenário: grupo inexistente no envio (RF-74)
  Dado o Keycloak com os grupos "rh" e "diretoria"
  Quando o curador envia um documento com o grupo "Sem restrição"
  Então a resposta é 422 listando "Sem restrição" e nenhum documento é criado

Cenário: grupo existente (RF-74)
  Quando o curador envia o documento com o grupo "rh" ou com "/rh"
  Então o documento é aceito e restrito a "rh"

Cenário: lista de grupos indisponível (RF-74, D3)
  Dado que o Keycloak não responde
  Quando o curador envia o documento com o grupo "rh"
  Então o documento é aceito e o log registra que a validação foi ignorada

Cenário: remover a restrição (RF-74)
  Quando o curador define a lista de grupos do documento como vazia
  Então a restrição é removida sem consultar o Keycloak
```

## Impacto arquitetural

- **Infraestrutura/LLM:** `HttpChatCompletionsLLM._open` passa a repetir conforme D2; a espera e a
  repetição de `sleep` são injetáveis para teste. Nenhuma mudança de contrato.
- **Aplicação:** serviço `validate_known_groups(groups, directory)` em
  `application/services/group_validation.py` e erro `UnknownGroupsError` (subclasse de
  `DomainValidationError`, 422 nas rotas que já traduzem esse erro). `IngestDocumentUseCase` e
  `SetDocumentGroupsUseCase` recebem o diretório de grupos de forma opcional (o comando de avaliação
  não o usa).
- **API:** as rotas de envio e de grupos do documento (`PUT /documents/{id}/groups`) injetam `get_group_directory`.
- **Dependências:** `backend/requirements.txt` passa a `qdrant-client==1.11.3`. A imagem precisa ser
  reconstruída (`docker compose build backend worker`).
- Banco: nenhuma migração. Variáveis novas: nenhuma.

## Estratégia de testes

| ID | Verifica | Nível |
|----|----------|-------|
| CT-71 | Repete em 503, 429 e falha de conexão e entrega na tentativa seguinte; esperas de 1 s e 3 s | Unitário |
| CT-72 | Não repete em 400, 401, 403 e 404; esgotadas as três tentativas devolve o erro atual | Unitário |
| CT-73 | O streaming repete só a abertura da conexão; depois do primeiro trecho não repete | Unitário |
| CT-74 | Grupo desconhecido recusado no envio e na restrição do documento, com os nomes recusados; nada gravado | Unitário |
| CT-75 | Grupo existente (com e sem barra inicial) aceito; lista vazia não consulta o diretório; diretório indisponível aceita e registra aviso | Unitário |
| CT-76 | A rota de envio responde 422 para grupo desconhecido, sem gravar (a restrição usa a mesma tradução de erro e é coberta por CT-74) | Integração (Docker) |
| CT-77 | Subida com `qdrant-client` 1.11.3 sem o aviso de versão; indexação e busca híbrida funcionam | Manual (campanha) |

## Riscos

- O `qdrant-client` 1.11.3 não foi executado contra o servidor neste ambiente (sem Docker na nuvem).
  A Query API com pré-buscas e fusão RRF existe desde a série 1.10; a validação real é o CT-77.
- Repetir amplia em até 4 s a espera de uma pergunta quando o provedor está instável; é o preço
  aceito em D2.
- Validar grupos depende do cliente de serviço `nexus-backend`. Sem ele (503 em `/groups`) a proteção
  não atua, por D3; resolver o realm continua necessário.
