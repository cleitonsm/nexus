# Plano de Implementação — SPEC-013 Várias chaves de LLM, modelo e parâmetros por assistente

**Spec**: [SPEC-20261027-013](SPEC-013-chaves-de-llm-e-parametros-por-assistente.md) (Aprovada em 2026-10-27)
**Status do plano**: Em andamento — P1 a P3 entregues
**Data**: 2026-10-27
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## 0. Andamento

| Pacote | Situação em 2026-10-27 | Verificado por |
|--------|------------------------|----------------|
| P0 Decisões | D1 a D10 escolhidas pelo autor em 2026-10-27 (todas as recomendações) | Registro na SPEC |
| P1 Domínio | Entregue: `LLMCredentialId` em `domain/value_objects.py`; `domain/llm_credentials.py` (`LLMModelOption`, `LLMCredential`, regras RN-37/RN-38, recuo da D11), `domain/retrieval_profile.py` (`RetrievalProfile`, `RetrievalDefaults`, `ResolvedRetrievalProfile`, `ParameterOrigin`), `Assistant` com credencial, modelo e perfil, porta `LLMCredentialRepository`, erro `LLMCredentialInUseError`, ações de auditoria novas | `test_llm_credentials` (42), `test_retrieval_profile` (15) |
| P2 Persistência | Entregue: migração `0010_llm_credentials` (tabela, nome único sem diferenciar maiúsculas, índice único parcial da padrão, FK `RESTRICT`, colunas no assistente, cópia da chave e do `llm_connection` para a credencial "Padrão" e volta no `downgrade`; as linhas antigas ficam até o P5, T9), `LLMCredentialModel`, `PostgresLLMCredentialRepository` (troca da padrão em duas instruções na mesma transação, com a linha travada; a padrão nunca sai pelo próprio `DELETE`; violação de índice ou FK vira erro de domínio, nunca 500), assistente com `update_llm_choice` e `update_retrieval_profile` (sem atualização perdida); conversão JSON em `infrastructure/llm_credential_mapping.py`, fora do pacote `database` para ser testada sem SQLAlchemy | `test_llm_credential_mapping` (9); CT-107 escrito em `tests/integration/test_llm_credentials_storage.py` (6 testes, inclusive as corridas que o banco fecha), a rodar no Docker |
| P3 Aplicação | Entregue: `manage_llm_credentials.py` (listar, opções para o assistente, criar, alterar com rotação, excluir, marcar padrão, impacto da troca da padrão para a D11, testar), `configure_assistant.py` (LLM e recuperação do assistente, com valor efetivo e origem), `services/llm_resolution.py` (RN-40, RN-41, D8, D11; chave decifrada só aqui), porta `SecretCipher` movida para o domínio. Os casos de uso da SPEC-008 saem junto com as rotas, no P5, para a API continuar importável até lá | `test_llm_credential_use_cases` (46) |
| P4 Pipeline do chat | Pendente | — |
| P5 API | Pendente | — |
| P6 Frontend | Pendente | — |
| P7 Documentação | Pendente | — |
| P8 Validação no Docker | Pendente | — |

Verificação feita fora do Docker, em Python 3.13 com o LangGraph substituído por um dublê:
**890 testes unitários passam** (778 anteriores e 112 novos). `ruff` não pôde ser instalado (sem
acesso ao PyPI); uma verificação equivalente à regra F401 (imports sem uso) não achou problemas.
Revisões do `architecture-guard`: P1 e P2/P3 sem bloqueantes; os achados importantes foram
corrigidos (P1: T3, T6, T7 e D11; P2/P3: T9, atualização perdida, corridas traduzidas, chave fora
do `repr` das entradas, 403 antes de 404, nome único sem diferenciar maiúsculas).
**Não verificado**: migração e repositórios no PostgreSQL real (CT-107, no Docker); nada do P2 e
do P3 é usado pelo chat, pela API ou pela tela até o P4 e o P5.

## 1. Ordem de execução

Fluxo `/spec-to-code`: testes antes do código em cada pacote. P1 a P4 mantêm o comportamento atual
quando nada está gravado (o objetivo de não regressão da SPEC), então podem ser entregues e
medidos antes da API e da tela.

```mermaid
flowchart LR
    P1[P1 Dominio] --> P2[P2 Persistencia e migracao 0010]
    P1 --> P3[P3 Casos de uso e resolucao]
    P2 --> P3
    P3 --> P4[P4 Pipeline do chat]
    P3 --> P5[P5 API]
    P5 --> P6[P6 Frontend]
    P4 --> P7[P7 Documentacao e ADR 0012]
    P6 --> P7
    P7 --> P8[P8 Validacao no Docker]
```

## 2. Pacotes

| Pacote | O que muda | Arquivos principais | Testes |
|--------|------------|---------------------|--------|
| **P1 Domínio** | `LLMCredential` com nome (até 100 caracteres), provedor, URL (regras da SPEC-008 D3 reaproveitadas de `llm_settings.py`), modelos sem duplicata, modelo padrão dentro da lista, padrão do sistema e chave configurada; `LLMModelOption` com preço opcional (entrada e saída juntos, não negativos, D8); `connection_for(model)` devolve a `LLMConnection` que o cliente HTTP já usa. Regras puras: `ensure_removable` (RN-38: padrão ou em uso por assistente → `LLMCredentialInUseError`), `ensure_models_removable` (modelo em uso), `default_after_change` (RN-37). `RetrievalProfile` com campos opcionais e faixas da D6; `validate_against(defaults)` recusa, ao gravar, top_k acima dos candidatos efetivos (T3); `resolve(defaults)` devolve valores efetivos e origem por campo e nunca falha na pergunta (top_k limitado aos candidatos, com `top_k_clamped`). `Assistant` ganha `llm_credential_id`, `llm_model` (com recuo da D11 quando segue a padrão) e `retrieval_profile`; `model_with_fallback` e `assistants_falling_back` (D11). Porta `LLMCredentialRepository`. Ações de auditoria da RF-94; as antigas (`llm_api_key.*`, `llm_settings.changed`) continuam no enum para a trilha já gravada. | `domain/llm_credentials.py`, `domain/retrieval_profile.py` (novos), `domain/entities.py`, `domain/interfaces.py`, `domain/errors.py`, `domain/audit.py`, `domain/__init__.py` | CT-99, CT-100, CT-101 e CT-102 (parte de domínio) |
| **P2 Persistência** | Migração `0010` (`/new-migration`): tabela `llm_credentials` (id, nome único, provedor, URL, modelos em JSON, modelo padrão, `is_default` com índice único parcial, ciphertext, autoria e datas); em `assistants`, `llm_credential_id` (FK `ON DELETE RESTRICT`), `llm_model` e `retrieval_profile` (JSON). Dados: cópia de `global_llm_api_key` e `llm_connection` para a credencial "Padrão" (D10), sem decifrar; `downgrade` devolve a padrão ao `app_settings`. `PostgresLLMCredentialRepository` (troca da padrão numa transação) e mapeamento das colunas novas em `PostgresAssistantRepository`. | `infrastructure/database/alembic/versions/0010_llm_credentials.py`, `infrastructure/database/models.py`, `infrastructure/database/repositories.py`, `infrastructure/database/operations_repositories.py` | CT-107 (integração) |
| **P3 Aplicação** | Casos de uso: listar, criar, alterar (com rotação opcional da chave), excluir, marcar padrão e testar credencial (só administrador, D7); `UpdateAssistantLLMUseCase` (administrador; modelo precisa estar na credencial); `UpdateAssistantRetrievalSettingsUseCase` e consulta com origem (administrador e curador do assistente). `resolve_llm_for_assistant` (RN-40) e `resolve_retrieval_settings` (RN-41) substituem `resolve_llm_connection` e o `retrieval_settings()` único. Auditoria sem a chave (RN-39). Saem os casos de uso da SPEC-008 (D9). | `application/use_cases/manage_llm_credentials.py`, `application/use_cases/configure_assistant.py` (novos), `application/services/llm_resolution.py` (novo), `application/services/access_control.py` | CT-101 a CT-105 |
| **P4 Pipeline do chat** | `chat_with_assistant` (com e sem streaming) recebe a conexão, a chave decifrada em memória, o preço do modelo e os parâmetros resolvidos por pergunta. `ContextRetriever` usa `candidates`, `top_n` e `min_score` do perfil; `VectorStoreGateway.search` ganha `hybrid: bool` (desligado = só prefetch denso, sem `FusionQuery`, mesmos filtros de `user_groups` e `active`). `HttpChatCompletionsLLM` criado por credencial. Consumo usa o preço do modelo ou `LLM_PRICE_*`. `evaluate` e `calibrate_relevance --assistant` usam a mesma resolução e registram credencial, modelo e parâmetros (RF-95). | `application/use_cases/chat_with_assistant.py`, `application/services/retrieval.py`, `infrastructure/vector_store/qdrant_store.py`, `api/dependencies.py`, `infrastructure/composition.py`, `cli/evaluate.py`, `cli/calibrate_relevance.py` | CT-106, CT-108 (integração), CT-111 (avaliação) |
| **P5 API** | `/admin/llm-credentials` (`GET`, `POST`), `/{id}` (`PUT`, `DELETE`), `/{id}/default` e `/{id}/test` (`POST`); `GET /llm-credentials/options`; `GET/PUT /assistants/{id}/llm` e `/assistants/{id}/retrieval-settings`. `LLMCredentialInUseError` → 409 com os assistentes afetados; códigos novos em `api/error_codes.py`. Saem `/admin/llm-settings` e `/admin/api-key*` (D9). | `api/routes/llm_credentials.py` (novo), `api/routes/assistants.py`, `api/routes/admin.py`, `api/schemas/` | CT-109 (integração) |
| **P6 Frontend** | Página `/admin/llm-credentials` no `administrationMenu` (lista, padrão com a lista de assistentes afetados antes de confirmar, criar, editar, rotacionar chave, testar, excluir, preço por modelo com aviso quando ausente). Seções "Modelo de linguagem" e "Recuperação" no assistente, com valor efetivo, origem, "restaurar padrão", aviso fixo dos filtros de segurança, de recalibração e de linha de base. Sai o formulário da SPEC-008. | `pages/llm-credentials-page.component.*` (novo), `pages/assistants-page.component.*`, `store/`, `core/services/nexus-api.service.ts`, `shared/models/nexus.models.ts` | CT-110 |
| **P7 Documentação** | ADR 0012 e status da ADR 0005 (substituída em parte) e 0007 (complementada); `estrategia-de-testes.md` com CT-99 a CT-112; `variaveis-ambiente.md` dizendo que `RETRIEVAL_CANDIDATES`, `RERANK_TOP_N`, `RELEVANCE_MIN_SCORE`, `LLM_MODEL` e `LLM_API_URL` viram padrão global; C4 de componentes; skill `desenvolvedor-nexus` (item 7 e ADRs vigentes). | `docs/arquitetura/adrs/`, `docs/especificacao/`, `docs/infraestrutura/`, `.claude/skills/desenvolvedor-nexus/SKILL.md` | — |
| **P8 Validação** | Docker: rebuild, migração `0010` sobre um banco com chave gravada (credencial "Padrão" criada, chat igual), CT-107 a CT-109, portão de qualidade nos três conjuntos sem configuração gravada (CT-111), CT-112 com OpenAI e Gemini reais em dois assistentes. Revisão do `architecture-guard` e do `rag-quality-reviewer`. | — | CT-107 a CT-112 |

## 3. Decisões técnicas deste plano

Escolhas de implementação que não mudam comportamento visível; ficam aqui para a revisão do autor.

| # | Escolha | Motivo |
|---|---------|--------|
| T1 | O preço do modelo guarda entrada e saída juntos ou nenhum dos dois; a moeda continua a de `LLM_PRICE_CURRENCY`. | Um preço só de entrada daria custo parcial sem aviso. |
| T2 | Substituída pela D11 da SPEC (autor, 2026-10-27): o assistente que segue a padrão pode guardar modelo, com recuo. | A revisão de arquitetura mostrou que a restrição mudava comportamento visível; virou decisão do autor. |
| T3 | A regra top_k ≤ candidatos vale sobre os valores efetivos (assistente ou padrão), conferida ao gravar. Na pergunta nunca há erro: se o ambiente mudou depois, top_k é limitado aos candidatos e o chat registra. | Um top_k gravado de 20 com candidatos do ambiente em 10 seria aceito campo a campo; recusar na pergunta derrubaria o chat do assistente. |
| T4 | Os valores do ambiente não passam pelas faixas da D6. | Hoje funcionam; recusar na subida mudaria o comportamento sem configuração gravada. |
| T5 | As ações de auditoria antigas ficam no enum. | A trilha já gravada continua legível na tela de auditoria. |
| T6 | `LLMCredential` recusa, em qualquer construção, URL com usuário/senha, parâmetros ou fragmento, e preset com URL diferente da do provedor. | RN-39: o repositório e a migração `0010` constroem sem passar por `build`; uma chave na URL vazaria na API e na auditoria. |
| T7 | Ao recusar a remoção da credencial padrão, o 409 lista também os assistentes que a seguem sem escolha. | A tela mostra quem seria afetado (risco da SPEC). |
| T8 | O curador do assistente consulta a credencial e o modelo efetivos (sem a chave); só o administrador altera. | A D7 restringe a escolha; a seção "Modelo de linguagem" (RF-92) aparece na tela que o curador já usa. |
| T9 | A `0010` só copia a chave e o `llm_connection`; as linhas antigas saem numa migração própria no P5, junto com as rotas da SPEC-008 (D9). A `0010` foi ajustada antes de ser aplicada em qualquer banco (só existe neste branch). | Até o P4 o chat ainda lê o caminho antigo; apagar antes deixaria o chat sem chave. |
| T10 | A migração lê `LLM_API_URL` e `LLM_MODEL` quando não há `llm_connection` gravado: o container que roda o Alembic (a API, na subida) precisa do mesmo ambiente. | D10. Registrar no P7/P8. |
