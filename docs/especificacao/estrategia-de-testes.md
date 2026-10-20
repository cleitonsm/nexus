# Estratégia de Testes — Evolução RAG Enterprise

Notação: `CT-XX` — Caso de Teste.
Este documento define como os requisitos RF-24 a RF-63 serão verificados. Os testes são escritos
**antes** da implementação de cada fase, a partir dos critérios de aceitação
(ver [`criterios-de-aceitacao.md`](criterios-de-aceitacao.md) e [`specs/`](specs/README.md)).

---

## Níveis de Teste

| Nível | Onde fica | O que cobre | Dependências |
|-------|-----------|-------------|--------------|
| Unitário (backend) | `backend/tests/unit` (`unittest`) | Domínio e casos de uso, com portas substituídas por dublês | Nenhuma: sem Docker, banco, Qdrant, Keycloak ou LLM real |
| Unitário (frontend) | `frontend/src/**/*.spec.ts` (Vitest) | Reducers, selectors, effects e guards | Nenhuma |
| Integração | `backend/tests/integration` | Adaptadores reais contra PostgreSQL, Qdrant e Keycloak em containers | Docker Compose |
| Avaliação de qualidade | `backend/tests/evaluation` | Recall@k, MRR, fidelidade e fallback contra o conjunto de referência | Docker Compose e LLM configurado |
| Ponta a ponta manual | `docs/qa/` | Roteiros de validação pela interface | Ambiente completo |

A proporção segue a pirâmide de testes: muitos unitários, integração nos pontos de contato com
infraestrutura e poucos roteiros ponta a ponta.

## Diretrizes

- Cada teste referencia o requisito ou a regra que verifica, no nome ou na docstring.
- Padrão Arrange–Act–Assert, um comportamento por teste.
- Casos normal, de limite e de erro para cada caso de uso, como já exigido no projeto.
- Dublês existentes são reaproveitados (`fake_llm`, `LocalHashEmbeddingGateway`); os novos
  adaptadores reais são exercitados apenas nos testes de integração.
- Cobertura mínima de 80% em `domain` e `application` (RNF-30).
- Nenhum teste é ignorado ou comentado sem justificativa registrada.

---

## Casos de Teste por Fase

### Fase 1 — Avaliação e linha de base

| ID    | Nível | Descrição | Verifica |
|-------|-------|-----------|----------|
| CT-01 | Unitário | Cálculo de recall@k e MRR com resultados conhecidos | RF-25 |
| CT-02 | Unitário | Item do conjunto de referência sem documento de origem é rejeitado | RF-24, RN-15 |
| CT-03 | Unitário | Comparação entre relatórios aponta regressão acima da tolerância | RF-26, RN-14 |
| CT-04 | Integração | Comando de avaliação gera relatório com commit, modelos e parâmetros | RF-25, RF-26 |
| CT-05 | Integração | Toda linha de log é JSON válido e contém o identificador da requisição | RF-27 |

### Fase 2 — Recuperação semântica

| ID    | Nível | Descrição | Verifica |
|-------|-------|-----------|----------|
| CT-06 | Unitário | Chunker não corta frases nem separa cabeçalho e linhas de uma tabela | RF-29 |
| CT-07 | Unitário | Nenhum chunk excede o limite de tokens configurado | RF-29 |
| CT-08 | Unitário | Cada chunk carrega seção, página e modelo de embedding; o documento registra modelo e versão do pipeline | RF-30, RF-32 |
| CT-09 | Unitário | Reindexação com falha mantém a collection vigente | RF-31 |
| CT-10 | Integração | Adaptador de embeddings real devolve vetores de 384 dimensões sem acesso à rede | RF-28, RNF-26 |
| CT-11 | Integração | Paráfrase recupera o trecho correto entre os cinco primeiros | RF-28, HU-17 |
| CT-12 | Integração | Troca de alias durante consultas concorrentes não gera erro | RF-31, RNF-18 |
| CT-13 | Avaliação | Recall@5 igual ou superior a 0,80 no assistente piloto | RNF-19 |

### Fase 3 — Busca híbrida, reranking e citações

| ID    | Nível | Descrição | Verifica |
|-------|-------|-----------|----------|
| CT-14 | Unitário | Nó de avaliação aciona fallback quando nenhum candidato atinge a nota mínima | RF-35, RN-17 |
| CT-15 | Unitário | Resposta sem citação válida é substituída pelo fallback | RF-37, RN-18 |
| CT-16 | Unitário | Histórico é truncado pelo orçamento preservando as mensagens recentes | RF-39, RN-19 |
| CT-17 | Unitário | Pergunta de continuação é reescrita com o tema do histórico (LLM fake) | RF-36 |
| CT-18 | Integração | Termo exato raro ("NR-35") é recuperado pela busca híbrida | RF-33, HU-19 |
| CT-19 | Integração | Reranker reordena candidatos e mantém os N melhores | RF-34 |
| CT-20 | Integração | Citações são persistidas com a mensagem e devolvidas pela API | RF-37 |
| CT-21 | Unitário (frontend) | Reducer armazena as fontes e o seletor as expõe por mensagem | RF-38 |
| CT-22 | Avaliação | Fidelidade igual ou superior a 0,90 e fallback correto igual ou superior a 90% | RNF-20, RNF-21 |

### Fase 4 — Autenticação e controle de acesso

| ID    | Nível | Descrição | Verifica |
|-------|-------|-----------|----------|
| CT-23 | Unitário | Token com assinatura, emissor, audiência ou validade incorretos é rejeitado | RNF-22 |
| CT-24 | Unitário | Política de acesso nega assistente sem grupo a usuário comum | RN-22 |
| CT-25 | Unitário | Restrição de documento não amplia o acesso do assistente | RN-23 |
| CT-26 | Integração | Todas as rotas, exceto `/health`, respondem 401 sem token | RF-40 |
| CT-27 | Integração | Usuário de outro grupo recebe 403 ao conversar com o assistente | RF-42 |
| CT-28 | Integração | Trecho de documento restrito não é recuperado para usuário não autorizado | RF-43, RNF-23 |
| CT-29 | Integração | Conversa de outro usuário responde 404 | RF-44, RN-24 |
| CT-30 | Integração | Rotas de administração da chave do LLM respondem 403 a não administradores, com papéis lidos do token | RF-41, RF-47 |
| CT-31 | Integração | Eventos de auditoria são gravados e não podem ser alterados | RF-45, RN-25 |
| CT-32 | Unitário (frontend) | Guard redireciona para o login sem sessão e oculta itens por papel | RF-46 |

### Fase 5 — Ingestão e ciclo de vida

| ID    | Nível | Descrição | Verifica |
|-------|-------|-----------|----------|
| CT-33 | Unitário | Upload registra documento "pendente", armazena o arquivo original e enfileira o job | RF-48, RF-49, RF-54 |
| CT-34 | Unitário | Arquivo com `content_hash` existente não gera novo documento | RF-52, RN-26 |
| CT-35 | Unitário | Terceira falha leva o documento ao estado "falhou" com motivo | RF-55, RN-30 |
| CT-36 | Unitário | Substituição mantém a versão anterior se a nova falhar | RF-51, RN-28 |
| CT-37 | Integração | Job reprocessado após queda do worker não duplica chunks | RNF-27 |
| CT-38 | Integração | Exclusão remove vetores por `document_id` e o arquivo original | RF-50, RN-29 |
| CT-39 | Integração | PDF digitalizado é indexado via OCR local | RF-53 |
| CT-40 | Integração | Upload de 25 MB responde em até 2 segundos | RNF-17 |

### Fase 6 — Operação e governança

| ID    | Nível | Descrição | Verifica |
|-------|-------|-----------|----------|
| CT-41 | Unitário | Limite de uso bloqueia a pergunta seguinte e informa a próxima janela | RF-59, RN-32 |
| CT-42 | Unitário | Instrução embutida em trecho recuperado não altera o prompt de sistema | RF-60, RN-31 |
| CT-43 | Unitário | Feedback negativo fica disponível ao curador como candidato | RF-61, RN-33 |
| CT-44 | Integração | Rastreamento contém um span por nó do grafo e o identificador da requisição; métricas de latência, tokens e custo são expostas | RF-56, RF-57, RNF-29 |
| CT-45 | Integração | Endpoint de streaming entrega a resposta em partes e as fontes ao final | RF-58 |
| CT-46 | Integração | Logs e spans não contêm token, chave de API nem texto integral de documento | RNF-25 |
| CT-47 | Integração | Restauração de backup em ambiente limpo recupera dados e buscas | RF-63, RNF-28 |
| CT-48 | Integração contínua | Avaliação com regressão simulada faz o pipeline falhar | RF-62 |

### SPEC-007 — Endurecimento

| ID | Nível | Descrição | Verifica |
|----|-------|-----------|----------|
| CT-58 | Unitário e integração | `POST /messages` recusa os papéis `assistant` e `system` (422) | RF-64 |
| CT-59 | Unitário | Upload lido em blocos: 413 pelo `Content-Length` e pelo fluxo, sem carregar o arquivo inteiro | RF-65 |
| CT-60 | Unitário e integração | Dois workers: quem perdeu a reserva não renova, não grava nem altera o alias; reserva renovada impede a devolução à fila | RF-66 |
| CT-61 | Unitário | Segredo ausente ou padrão fora de `APP_ENV=local` impede a partida, sem citar o valor | RF-67 |
| CT-62 | Unitário | O comando de avaliação envia e processa os documentos do piloto; falha de indexação é reportada | CT-04 |
| CT-63 | Unitário | `LLMConnection` aceita presets e URL personalizada válida; recusa modelo vazio, com espaço ou longo, URL sem `https`, com usuário/senha, parâmetros ou fragmento | RF-69 |
| CT-64 | Unitário | Resolução: sem valor gravado vale o ambiente (provedor inferido pela URL); o gravado vence | RF-68, RF-70 |
| CT-65 | Unitário | Consulta e alteração exigem administrador; a negativa é auditada | RF-71 |
| CT-66 | Unitário | A alteração grava, audita anterior e novo sem a chave e vale na resolução seguinte | RF-69, RF-71 |
| CT-67 | Unitário | Preset fixa a URL do provedor mesmo que o cliente envie outra; `http` só no ambiente local | RF-69 |
| CT-68 | Integração | `GET` e `PUT /admin/llm-settings`: 200, 422 e 403 | RF-68, RF-69, RF-71 |
| CT-69 | Vitest | Reducer e seletor da conexão (carregada, salva, erro) | RF-72 |
| CT-70 | Manual | Gemini real: "Testar LLM" responde `ok` com a chave de teste do autor | RF-70 |
| CT-71 | Unitário | O cliente do LLM repete em 503, 429 e falha de conexão e entrega na tentativa seguinte, esperando 1 s e 3 s | RF-73 |
| CT-72 | Unitário | Não repete em 400, 401, 403 e 404; esgotadas as três tentativas devolve o erro atual | RF-73 |
| CT-73 | Unitário | O streaming repete só a abertura da conexão; depois que o provedor respondeu não repete | RF-73 |
| CT-74 | Unitário | Grupo desconhecido recusado no envio e na restrição do documento, com os nomes recusados; nada é gravado | RF-74 |
| CT-75 | Unitário e integração | Grupo existente (com e sem barra inicial) aceito; lista vazia não consulta o Keycloak; Keycloak indisponível aceita e registra aviso | RF-74 |
| CT-76 | Integração | A rota de envio responde 422 para grupo desconhecido, sem gravar | RF-74 |
| CT-77 | Manual | Subida com `qdrant-client` 1.11.3 sem o aviso de versão; indexação e busca híbrida funcionam | SPEC-009 D1 |

---

## Testes de Segurança Recorrentes

Executados a cada mudança nas fases 4 a 6, por serem os de maior impacto em caso de falha:

- isolamento entre assistentes (já existente no MVP) e entre grupos (CT-27, CT-28);
- privacidade de conversas (CT-29);
- ausência de segredos em logs e respostas (CT-46 e os testes do ADR 0005);
- validação de token (CT-23, CT-26).

## Critério de Conclusão de uma Fase

Uma fase só é considerada concluída quando:

1. a especificação SDD correspondente está com status `Aprovada` e depois `Implementada`;
2. todos os casos de teste da fase passam, sem testes ignorados;
3. a avaliação de qualidade não apresenta regressão (RN-14);
4. ADRs, diagramas e documentos de infraestrutura afetados foram atualizados;
5. o roteiro manual em [`docs/qa/validacao-manual-rag-enterprise.md`](../qa/validacao-manual-rag-enterprise.md) foi executado para a fase.

---

## Situação dos Casos de Teste

Atualizado em 2026-10-20. "Executado no Docker" remete ao [registro da rodada de integração](../qa/relatorios/2026-10-16-rodada-integracao/LEIAME.md)
(2026-10-15/16) ou aos logs de `docs/qa/relatorios/2026-10-19-*` e `2026-10-20-*`. Nada disso substitui a
campanha V0 a V8: na V3 o orquestrador roda **toda** a pasta `backend/tests/integration` e reprova se algum
teste for pulado.

### Executados com sucesso

| Casos | Onde rodou | Onde |
|-------|------------|------|
| CT-01 a CT-03, CT-05 (parte unitária), CT-06 a CT-09, CT-14 a CT-17, CT-23 a CT-25, CT-33 a CT-36, CT-41 a CT-43, CT-58, CT-59, CT-61 a CT-67, CT-71 a CT-75 | Unitários (662 testes, 1 pulado; 2026-10-20 sobre `95c49ff`) | `backend/tests/unit/` |
| CT-46 | Sem Docker e no CI | `backend/tests/integration/test_sensitive_data_leak.py` |
| CT-48 (comparação) | Unitário | `backend/tests/unit/test_regression_gate.py` |
| CT-28, CT-31 e a purga de retenção (D6) | Docker, 2026-10-16 | `test_access_control_storage.py` |
| CT-75 e CT-76 (rota) e as rotas de documentos | Docker, 2026-10-16 (14 testes) | `test_api_routes.py` |
| CT-39 (OCR em português no container) | Docker, 2026-10-16 | `test_ocr_container.py` |
| CT-40 (upload de ~25,3 MB em até 2 s) | Docker, 2026-10-16 | `test_upload_latency.py` |
| CT-49 (parcial: `upgrade head`, `check`, downgrade e upgrade da `0008`, trilha de auditoria preservada) | Docker, 2026-10-16 | `alembic`; registro da rodada |
| CT-50, CT-51, CT-57 | Docker, 2026-10-16 | `test_full_stack_flow.py`, `test_assistant_isolation.py`, `test_consistency_check.py` |
| CT-53 (worker interrompido conclui ou retoma o job) | Docker, 2026-10-20, depois de `df8d445` e `95c49ff` (reprovado em 2026-10-19) | `scripts/validation/worker_resilience.sh`, `ct53_driver.py` |
| CT-54 (operação sem internet, avaliação sem LLM e OCR) | Docker, 2026-10-19 | `scripts/validation/offline_check.sh` |
| CT-21, CT-32, CT-69 e FE-01 a FE-05 | `npm test` no container `node:22`, 2026-10-16 (16 arquivos, 149 testes) | `frontend/src/**/*.spec.ts` |
| CT-22 (curva no `nexus-docs`, 27 itens) | Docker, 2026-10-16; decisão `RELEVANCE_MIN_SCORE=0,10` | `backend/tests/evaluation/reports/nexus-docs/calibracao.json` |

### Escritos, a executar (V3, V7 ou V8 da campanha, salvo indicação)

| Casos | Observação | Onde |
|-------|------------|------|
| CT-04 | Exige PostgreSQL e Qdrant | `test_evaluation_command.py` |
| CT-05 (com a API) | — | `test_request_context.py` |
| CT-07 (tokenizador real), CT-10, CT-11 | Exigem o modelo | `test_semantic_embedding.py` |
| CT-12 | Exige o Qdrant | `test_qdrant_alias.py` |
| CT-18, CT-19 | Exigem o Qdrant e os modelos; a parte sem eles roda em `test_retrieval_components.py` | `test_hybrid_search.py` |
| CT-20, CT-45 | — | `test_chat_citations.py` |
| CT-26, CT-27, CT-29, CT-30, CT-58 (rota), CT-68 | Os contratos com dublês rodam nos unitários | `test_access_control_api.py` |
| CT-37, CT-38 | — | `test_document_lifecycle_storage.py` |
| CT-44 | — | `test_operations_api.py` |
| CT-60 (`UPDATE` condicionais no PostgreSQL) | Dois workers simulados já passam nos unitários | `test_job_ownership_storage.py` |
| D10 da SPEC-006 (pausa da ingestão) | — | `test_ingestion_pause_storage.py` |
| CT-49 (completo) | — | `test_migrations.py` |
| CT-52 | Exige o cliente `nexus-tests` no realm | `test_keycloak_real.py` |
| CT-55 | Na V3 usa `http://frontend` pela rede do Compose; fora dela, `NGINX_URL` | `test_nginx_proxy.py` |
| CT-56 | Roda no container (V3) | `scripts/validation/leakage_scan.py` |
| CT-47 | V8; os scripts já passaram no ensaio com PostgreSQL real e Qdrant simulado | `scripts/validation/backup-restore.sh` |
| CT-48 (roteiro com o código de saída real) | V8 | `scripts/validation/regression-gate.sh` |
| CT-13 e as metas de qualidade | V6, com LLM, depois da validação dos 55 itens do `nexus-docs-ampliado` e da nova calibração | `scripts/eval.sh` |
| RNF-03, RNF-16, RNF-18 | V7 (100.000 trechos; RNF-18 exige `NEXUS_REINDEX_ASSISTANT_ID`) | `scripts/perf/retrieval_latency.py`, `reindex_under_load.py` |
| RNF-01 (TTFT) | Fora do orquestrador, depois da V6 | `scripts/perf/ttft.py` |
| CT-70 | Gemini real, com a chave do autor | — |
| CT-77 | Aviso de versão do Qdrant, depois de reconstruir as imagens | — |
| FE-06, FE-07 | Exigem o Playwright, que não está no `package.json` | `frontend/e2e/` |

Ferramentas de medição e orquestração: `scripts/perf/`, `scripts/validation/run-all.sh`, testadas sem Docker
em `test_perf_tools.py` e `test_validation_runner.py`.

Os testes de integração da Fase 4 não sobem o Keycloak: usam o verificador de token real com
tokens assinados por uma chave gerada no próprio teste.

A suíte unitária soma 662 testes (2026-10-20). Fora do Docker ela roda com o LangGraph substituído por um
dublê local; dentro do container, na V2 da campanha.

O projeto utiliza `unittest`, sem dependência adicional de framework de testes.
