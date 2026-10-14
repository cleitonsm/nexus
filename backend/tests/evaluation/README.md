# Avaliação de Qualidade do RAG

Implementa a [SPEC-001](../../../docs/especificacao/specs/SPEC-001-avaliacao-e-linha-de-base.md):
mede o pipeline de RAG contra um conjunto de referência e compara com a execução anterior.

## Estrutura

- `datasets/<nome>.jsonl`: conjunto de referência, um item por linha.
- `reports/<nome>/<data>-<commit>.json`: relatório de cada execução, com resumo `.md` ao lado.

## Formato do conjunto de referência

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `id` | sim | Identificador estável e único do item |
| `question` | sim | Pergunta como um usuário real faria |
| `expected_answer` | sim, exceto fora de escopo | Resposta de referência |
| `source_documents` | sim, exceto fora de escopo | Nomes dos arquivos que contêm a resposta |
| `out_of_scope` | não | `true` para perguntas que devem resultar em fallback |
| `validated_by` | sim | Curador que validou o item (RN-15) |
| `history` | não | Turnos anteriores (`[{"role": "user" ou "assistant", "content": "..."}]`) de uma pergunta de continuação. Com LLM, a pergunta é reescrita com eles antes da busca (RF-36); com `--no-generation`, segue como foi escrita |

Um conjunto com qualquer item inválido é rejeitado por inteiro e nenhuma métrica é calculada.

## Conjunto piloto

`datasets/nexus-docs.jsonl` contém 27 perguntas (22 dentro do escopo e 5 fora) sobre os arquivos
de `docs/negocio` e `docs/arquitetura` deste repositório.

As perguntas foram redigidas com apoio de IA e **validadas pelo autor, como curador, em
2026-10-07**, com três ajustes nas fontes (`neg-03`, `neg-05` e `arq-04`). Limitações conhecidas
do conjunto: está abaixo da meta de 50 a 100 itens; as perguntas foram escritas por quem leu os
documentos, o que tende a favorecer a recuperação; e `neg-09` e `arq-01` tratam do mesmo tema.

Ao acrescentar itens, preencha `validated_by` com o nome de quem validou. Para testar um rascunho
ainda não validado, use `--allow-unvalidated`; o relatório registra que o conjunto não foi validado.

## Conjunto ampliado (rascunho)

`datasets/nexus-docs-ampliado.jsonl` reúne os 27 itens validados e **55 rascunhos** redigidos com apoio
de IA em 2026-10-14 (82 itens: 62 dentro e 20 fora do escopo), com 11 perguntas de termo exato, 9 de
continuação (`history`), 9 sobre tabelas de DOCX e 15 fora do escopo, 4 delas perto do domínio
(por exemplo, a diária de um cargo que a tabela não tem). Os documentos DOCX são fictícios e ficam em
`fixtures/`.

Os rascunhos **não estão validados**: cada um traz `origem` e não tem `validated_by`, então o comando
os recusa. Revise cada item (pergunta, resposta esperada e fontes), corrija o que for preciso e registre
a validação:

```powershell
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --list
python backend\tests\evaluation\validate_items.py backend\tests\evaluation\datasets\nexus-docs-ampliado.jsonl --by "Seu Nome" --approve te-01 te-02
```

`scripts\eval.ps1 nexus-docs-ampliado` usa um assistente próprio ("Nexus Docs Ampliado (avaliacao)"), para
não alterar a base do piloto, e indexa também os arquivos de `fixtures/`. Para testar antes de validar,
acrescente `--allow-unvalidated` (o relatório registra que o conjunto não foi validado).

## Como executar

Com o ambiente no ar (`docker compose up -d --build`):

```bash
# Linux, macOS ou Git Bash
scripts/eval.sh nexus-docs
```

```powershell
# Windows PowerShell
scripts\eval.ps1 nexus-docs
```

Na primeira execução o comando cria o assistente "Nexus Docs (avaliacao)" e indexa os arquivos
`.md` de `docs/negocio` e `docs/arquitetura`. Nas seguintes, reutiliza a base existente; para
reindexar depois de alterar os documentos, exclua o assistente pela interface.

A partir da Fase 2, se a base do piloto tiver sido gerada por outro modelo de embedding ou por
outra versão do pipeline, o comando a descarta e a reconstrói a partir dos mesmos diretórios. O
relatório registra o modelo, a versão do pipeline e os parâmetros de chunking.

### Linha de base anterior à Fase 2

O pipeline do MVP (hash de palavras e corte de 700 caracteres) deixou de existir no código. Para
registrar a linha de base com ele, execute a avaliação no commit `9dcf007` e volte ao ramo:

```bash
git stash -u            # se houver alterações locais
git checkout 9dcf007
docker compose up -d --build
scripts/eval.sh nexus-docs --no-generation
git checkout feat/rag-enterprise-fase-1
docker compose up -d --build
scripts/eval.sh nexus-docs --no-generation
```

O segundo relatório é comparado automaticamente com o primeiro.

Opções úteis:

- `--no-generation`: mede apenas a recuperação (recall@k e MRR), sem chamar o LLM.
- `--k 5`: profundidade em que a recuperação é medida, já depois do reranking. O tamanho do
  contexto vem de `RERANK_TOP_N`, `RELEVANCE_MIN_SCORE` e `CONTEXT_TOKEN_BUDGET`, como no chat.
- `--tolerance 0.02`: regressão máxima aceita; o padrão vem de `EVAL_REGRESSION_TOLERANCE`.

Sem chave de LLM configurada, a geração é ignorada automaticamente.

## Calibração da nota mínima (CT-22)

Com o piloto já indexado por `scripts\eval.ps1`, `scripts\calibrate.ps1 nexus-docs` varre a nota
mínima de 0,05 a 0,95 usando as notas reais do reranker, **sem chamar o LLM**. Para cada nota mostra
quanto das perguntas dentro do escopo ainda encontram a fonte correta e quanto das perguntas fora do
escopo termina em fallback, além da média das duas e dos itens problemáticos. O resumo também é salvo
em `reports/<conjunto>/calibracao.json`. O comando não altera nenhuma configuração: o valor de
`RELEVANCE_MIN_SCORE` é decisão de quem opera o sistema.

## Métricas

| Métrica | Definição |
|---------|-----------|
| `recall_at_k` | Proporção de perguntas com ao menos um trecho de um documento de origem entre os k primeiros |
| `mrr` | Média do inverso da posição do primeiro trecho correto |
| `faithfulness` | Proporção de respostas sustentadas pelo contexto, julgadas pelo LLM configurado |
| `fallback_accuracy` | Proporção de perguntas fora de escopo que resultaram em fallback |
| `citation_coverage` | Proporção das perguntas dentro do escopo respondidas com ao menos uma citação válida (RN-18); vazio sem geração |

## Código de saída

| Código | Significado |
|--------|-------------|
| 0 | Avaliação concluída, sem regressão |
| 1 | Alguma métrica caiu além da tolerância em relação ao relatório anterior |
| 2 | Conjunto de referência inválido |
| 3 | Algum documento do piloto não chegou a `indexado` (ver o log `evaluation.seed.failed`) |

## Limitações conhecidas

- A fidelidade usa o mesmo `LLM_MODEL` das respostas, com a temperatura fixa do adaptador (0,2),
  e não zero como previa a especificação; o resultado pode variar entre execuções.
- O caso de uso reproduz a decisão de fallback do grafo do chat sem persistir mensagens. Se o
  grafo mudar, `EvaluateAssistantUseCase` precisa acompanhar.
- O relatório de linha de base é versionado; os demais relatórios podem ficar fora do Git.
