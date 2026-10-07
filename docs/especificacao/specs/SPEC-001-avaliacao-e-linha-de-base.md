# Spec: Avaliação e Linha de Base

**ID**: SPEC-20261007-001
**Status**: Aprovada em 2026-10-07 por Cleiton Medeiros — implementação entregue, aguardando validação no ambiente Docker
**Autor**: Cleiton Medeiros (elaborada com apoio de IA generativa; aprovada pelo autor)
**Data**: 2026-10-07
**Fase**: 1 de 6 — etapa 9 do [plano incremental](../../plano-incremental.md)

## Contexto e Problema

O pipeline de RAG do MVP não possui nenhuma medida de qualidade. Não há como afirmar que uma
mudança de modelo, de chunking ou de prompt melhorou as respostas, nem como detectar regressões.
Além disso, o único registro de execução é um arquivo de depuração gravado dentro do container
(`debug-a1f259.log`), sem estrutura e sem identificador de requisição.

Esta fase cria o instrumento de medida que orienta todas as fases seguintes e registra a linha de
base do pipeline atual (embedding por hash, corte fixo de 700 caracteres, busca densa simples).

## Requisitos Funcionais

- [ ] RF-24: conjunto de referência versionado por assistente.
- [ ] RF-25: comando de avaliação com recall@k, MRR, fidelidade e taxa de fallback correto.
- [ ] RF-26: relatório por execução, com comparação à execução anterior.
- [ ] RF-27: logs estruturados em JSON com identificador de requisição.

## Requisitos Não Funcionais

- [ ] RNF-25: logs sem segredos, tokens ou conteúdo integral de documentos.
- [ ] RNF-29: identificador único por requisição, propagado por todas as etapas.
- [ ] RNF-30: componentes novos atrás de portas do domínio; cobertura mínima de 80%.

## Regras de Negócio

- RN-14: mudança em recuperação ou geração exige avaliação registrada, sem regressão.
- RN-15: conjunto de referência validado por curador.

## Critérios de Aceite (Gherkin)

```gherkin
Funcionalidade: Avaliação do pipeline de RAG

  Cenário: Gerar relatório de avaliação
    Dado que existe um conjunto de referência válido para o assistente piloto
    Quando a equipe técnica executa o comando de avaliação
    Então o relatório apresenta recall@5, MRR, fidelidade e taxa de fallback correto
    E o relatório identifica commit, modelo de embedding, modelo de LLM e parâmetros de busca

  Cenário: Rejeitar conjunto de referência inválido
    Dado que um item do conjunto não possui documento de origem
    Quando a avaliação é executada
    Então o comando encerra listando os itens inválidos
    E nenhuma métrica é calculada

  Cenário: Detectar regressão
    Dado que existe um relatório anterior com recall@5 de 0,80
    E a tolerância configurada é de 0,02
    Quando uma nova avaliação resulta em recall@5 de 0,70
    Então o comando termina com código de erro
    E o relatório destaca a métrica que regrediu

  Cenário: Rastrear uma requisição pelos logs
    Dado que um usuário enviou uma pergunta ao chat
    Quando os logs do backend são consultados pelo identificador da requisição
    Então todas as linhas dessa requisição são JSON válido com o mesmo identificador
    E nenhuma linha contém a chave de API nem o texto integral de um documento
```

## Design da Solução

### Conjunto de referência

Arquivos JSON Lines em `backend/tests/evaluation/datasets/<slug-do-assistente>.jsonl`, um item
por linha:

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `id` | sim | Identificador estável do item |
| `question` | sim | Pergunta como um usuário real faria |
| `expected_answer` | sim, exceto fora de escopo | Resposta de referência validada pelo curador |
| `source_documents` | sim, exceto fora de escopo | Nomes dos documentos que contêm a resposta |
| `out_of_scope` | não | `true` para perguntas que devem resultar em fallback |
| `validated_by` | sim | Curador que validou o item |

Meta inicial: 50 a 100 itens por assistente piloto, sendo de 10% a 20% fora de escopo. Os dados
devem ser fictícios ou públicos; nenhum documento real ou confidencial entra no repositório.

### Métricas

| Métrica | Definição |
|---------|-----------|
| Recall@k | Proporção de perguntas em que ao menos um chunk de um documento de origem aparece entre os k primeiros |
| MRR | Média do inverso da posição do primeiro chunk correto |
| Fidelidade | Proporção de respostas cujas afirmações são sustentadas pelo contexto recuperado, julgada por LLM com rubrica fixa |
| Fallback correto | Proporção de perguntas fora de escopo que resultaram em fallback |

Recall@k e MRR dependem apenas de embeddings e vector store e podem rodar sem LLM. Fidelidade usa
o `LLMGateway` já configurado; a rubrica do juiz é versionada junto com o código.

### Componentes

| Camada | Componente | Responsabilidade |
|--------|------------|------------------|
| Domínio | `EvaluationItem`, `EvaluationReport` (dataclasses congeladas) | Estrutura do conjunto e do resultado |
| Domínio | `AnswerJudge` (Protocol) | Julgar fidelidade de uma resposta ao contexto |
| Aplicação | `EvaluateAssistantUseCase` | Executar recuperação e geração para cada item e calcular as métricas |
| Aplicação | `CompareEvaluationReportsUseCase` | Comparar com o relatório anterior e aplicar a tolerância |
| Infraestrutura | `LLMAnswerJudge` | Implementar `AnswerJudge` sobre o `LLMGateway` |
| Infraestrutura | `JsonlEvaluationDatasetLoader` | Ler e validar o conjunto de referência |
| Infraestrutura | `logging` estruturado e middleware de identificador de requisição | Atender RF-27 |
| Scripts | `scripts/eval.sh` | Executar a avaliação dentro do container do backend |

O caso de uso de avaliação reutiliza as mesmas portas do chat (`EmbeddingGateway`,
`VectorStoreGateway`, `LLMGateway`), de modo que mede o pipeline real, não uma cópia.

### Relatório

Gravado em `backend/tests/evaluation/reports/<assistente>/<data>-<commit>.json`, com resumo em
Markdown. Contém métricas, parâmetros, lista de perguntas que falharam e diferença em relação ao
relatório anterior. Os relatórios de linha de base são versionados; os demais ficam fora do Git.

### Logs estruturados

- Um middleware FastAPI gera ou aceita o cabeçalho `X-Request-ID` e o disponibiliza por contexto.
- O formato de log passa a ser JSON com `timestamp`, `level`, `request_id`, `event` e campos do evento.
- A função `_agent_debug_log` e o arquivo `debug-a1f259.log` são removidos.
- Campos de conteúdo são truncados; chaves e tokens nunca são registrados.

## Impacto Arquitetural

- Camadas afetadas: domínio (novos tipos e uma porta), aplicação (dois casos de uso),
  infraestrutura (juiz, leitor de conjunto, logging) e API (middleware).
- Nenhum serviço novo no Docker Compose.
- ADR relacionada: [0010 — Observabilidade e avaliação contínua](../../arquitetura/adrs/0010-observabilidade-e-avaliacao-continua.md).

## Estratégia de Testes

- Unitários: CT-01, CT-02, CT-03.
- Integração: CT-04, CT-05.
- Resultado esperado da fase: relatório de linha de base do pipeline atual registrado no repositório.

## Riscos e Dependências

- Depende de um curador para validar perguntas e respostas (risco R14).
- O juiz de fidelidade é um LLM e pode ser inconsistente; mitigação: rubrica fixa, temperatura
  zero e amostra revisada manualmente.
- A avaliação de fidelidade consome chamadas ao LLM; recall@k e MRR devem poder rodar isoladamente.

## Decisões Tomadas

Registradas em 2026-10-07, na aprovação da especificação.

| Decisão | Escolha |
|---------|---------|
| Assistente piloto e origem dos documentos de teste | Documentação do próprio Nexus (`docs/negocio` e `docs/arquitetura`) |
| Tolerância de regressão | 0,02, configurável por `EVAL_REGRESSION_TOLERANCE` |
| Modelo usado como juiz | O mesmo `LLM_MODEL`, pelo `LLMGateway` já configurado |

## Situação da Implementação

| Requisito | Situação |
|-----------|----------|
| RF-24 | Implementado. Conjunto piloto com 27 itens em `backend/tests/evaluation/datasets/nexus-docs.jsonl`, validado por Cleiton Medeiros em 2026-10-07, com três ajustes nas fontes; abaixo da meta de 50 a 100 itens |
| RF-25 | Implementado: `EvaluateAssistantUseCase` e `python -m src.cli.evaluate`, com `scripts/eval.sh` e `scripts/eval.ps1` |
| RF-26 | Implementado: `JsonEvaluationReportStore` e `CompareEvaluationReportsUseCase` |
| RF-27 | Implementado: `JsonLogFormatter`, middleware de `X-Request-ID` e remoção de `_agent_debug_log` |

Testes: CT-01, CT-02 e CT-03 em `backend/tests/unit/test_evaluation.py`; a parte unitária de
CT-05 em `backend/tests/unit/test_structured_logging.py`; CT-05 com a API em
`backend/tests/integration/test_request_context.py`.

### Pendências para marcar como Implementada

- Executar os testes de integração e o comando de avaliação no ambiente Docker (CT-04 e CT-05);
  até aqui só os testes unitários foram executados.
- Ampliar o conjunto de referência para a meta de 50 a 100 itens, com perguntas de quem não
  redigiu os documentos.
- Registrar no repositório o relatório de linha de base gerado no ambiente Docker.

### Desvios em relação ao desenho

- O juiz de fidelidade usa a temperatura fixa do adaptador de LLM (0,2), não zero: alterar a
  temperatura exigiria mudar a porta `LLMGateway`, fora do escopo desta fase.
- O caso de uso de avaliação reproduz a decisão de fallback do grafo do chat em vez de invocá-lo,
  para não gravar conversas de teste no banco.
- Os relatórios são gravados em `reports/<conjunto>/`, e não em `reports/<assistente>/`.
- Os logs do servidor HTTP passam pelo mesmo formato JSON; o log de acesso do Uvicorn é
  substituído pelo evento `http.request.finished`.

### Linha de base indicativa

Simulação fora do Docker, com a mesma ingestão e o mesmo embedding por hash, busca por cosseno em
memória e o conjunto piloto validado (15 documentos, 94 chunks, em 2026-10-07):

| Métrica | Valor |
|---------|-------|
| recall@5 | 0,59 |
| MRR | 0,39 |
| Perguntas fora de escopo que receberam contexto | 5 de 5 |

Como a busca atual sempre devolve trechos, nenhuma pergunta fora de escopo chegaria ao fallback
pela regra vigente. A medição anterior, com o conjunto ainda não validado e 87 chunks, havia
resultado em recall@5 de 0,50: os documentos do piloto são os próprios documentos do projeto, de
modo que cada atualização da documentação altera a base e o resultado. Estes números são apenas indicativos; a linha de base oficial é a gerada por
`scripts/eval.sh` no ambiente Docker.
