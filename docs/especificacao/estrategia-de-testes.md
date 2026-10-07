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

Atualizado em 2026-10-07.

| Casos | Situação | Onde |
|-------|----------|------|
| CT-01, CT-02, CT-03 | Implementados e executados com sucesso | `backend/tests/unit/test_evaluation.py` |
| CT-05 (formato e identificador) | Parte unitária implementada e executada com sucesso | `backend/tests/unit/test_structured_logging.py` |
| CT-05 (com a API) | Implementado, ainda não executado | `backend/tests/integration/test_request_context.py` |
| CT-04 | Depende da execução de `scripts/eval.sh` no ambiente Docker, ainda não realizada | `backend/tests/evaluation/` |
| CT-06, CT-07 | Implementados e executados com sucesso, com contador de tokens dublê | `backend/tests/unit/test_structural_chunker.py` |
| CT-08 | Parcial: seção e página por chunk; modelo e versão do pipeline dependem da ligação à ingestão | `backend/tests/unit/test_structural_chunker.py` |
| CT-09 a CT-48 | Não implementados; pertencem às Fases 2 a 6 | — |

A suíte unitária soma 143 testes (21 do MVP, 53 da Fase 1 e 69 da Fase 2). Ela foi executada fora do Docker, com
o LangGraph substituído por um dublê local; a execução dentro do container ainda está pendente.

O projeto utiliza `unittest`, sem dependência adicional de framework de testes.
