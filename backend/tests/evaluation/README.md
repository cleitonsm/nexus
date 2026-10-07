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

Opções úteis:

- `--no-generation`: mede apenas a recuperação (recall@k e MRR), sem chamar o LLM.
- `--k 5` e `--context-top-k 4`: profundidade da busca e tamanho do contexto.
- `--tolerance 0.02`: regressão máxima aceita; o padrão vem de `EVAL_REGRESSION_TOLERANCE`.

Sem chave de LLM configurada, a geração é ignorada automaticamente.

## Métricas

| Métrica | Definição |
|---------|-----------|
| `recall_at_k` | Proporção de perguntas com ao menos um trecho de um documento de origem entre os k primeiros |
| `mrr` | Média do inverso da posição do primeiro trecho correto |
| `faithfulness` | Proporção de respostas sustentadas pelo contexto, julgadas pelo LLM configurado |
| `fallback_accuracy` | Proporção de perguntas fora de escopo que resultaram em fallback |

## Código de saída

| Código | Significado |
|--------|-------------|
| 0 | Avaliação concluída, sem regressão |
| 1 | Alguma métrica caiu além da tolerância em relação ao relatório anterior |
| 2 | Conjunto de referência inválido |

## Limitações conhecidas

- A fidelidade usa o mesmo `LLM_MODEL` das respostas, com a temperatura fixa do adaptador (0,2),
  e não zero como previa a especificação; o resultado pode variar entre execuções.
- O caso de uso reproduz a decisão de fallback do grafo do chat sem persistir mensagens. Se o
  grafo mudar, `EvaluateAssistantUseCase` precisa acompanhar.
- O relatório de linha de base é versionado; os demais relatórios podem ficar fora do Git.
