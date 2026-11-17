# ADR 0015: GenAI no pipeline de CI/CD

## Status

Proposta em 2026-11-17, aguardando aprovação. Não altera a [SPEC-006](../../especificacao/specs/SPEC-006-operacao-e-governanca.md)
D4 para o workflow `ci`: ele continua sem chave de LLM. Esta ADR cria uma exceção restrita ao workflow
`nexus-devops`.

## Contexto

Hoje o pipeline do Nexus falha de forma binária. Quando o lint ou os testes quebram, o PR mostra só
"failed", e quem o abriu precisa abrir o log do job, achar o traceback no meio de centenas de linhas e
ligá-lo ao trecho alterado. Isso pesa mais em erros que compilam e só aparecem na execução (tipo errado,
cálculo errado) e em mudanças que afrouxam o isolamento por grupos, cujo risco de segurança nem sempre
fica evidente no teste que falhou.

Outros dois pontos repetem o mesmo padrão de trabalho manual:

- PRs verdes chegam sem resumo das mudanças, e a documentação (SPEC, ADR, `.env.example`) fica para trás.
- Um alerta de observabilidade (tempo até o primeiro token, fila de ingestão, suspeita de injeção de
  prompt) exige cruzar métricas, logs e commits recentes antes de qualquer ação.

Um LLM pode fazer a primeira leitura desses dados e devolver um diagnóstico em linguagem natural dentro
do próprio PR ou de uma issue, reduzindo o tempo até entender o problema. A SPEC-006 D4, porém, decidiu
que nenhuma chave de LLM vira segredo no GitHub. Rodar o agente no pipeline exige guardar uma chave lá.

## Decisão

1. **Workflow separado.** `.github/workflows/nexus-devops.yml`, com os jobs `lint` e `unit_test`
   (build e teste), `ai_debugger` (`if: failure()`), `ai_change_summary` (`if: success()`),
   `deploy_staging` (após o `ci` verde num push para a `main`) e `ai_incident` (`repository_dispatch`
   do tipo `alerta-observabilidade` ou cenário fictício). O `ci.yml` não muda.
2. **IA consultiva.** O agente (`scripts/nexus_devops/analista.py`) sempre sai com sucesso: sem
   `GENAI_API_KEY`, com o LLM fora do ar ou com erro na API do GitHub, ele registra um aviso no resumo do job.
   Nenhuma decisão de merge ou deploy depende da IA.
3. **Segredo isolado.** Uma chave própria do pipeline (`GENAI_API_KEY`), com limite de gasto no
   provedor, diferente das credenciais do Nexus (ADR 0013). O endpoint é qualquer `/chat/completions`
   compatível com OpenAI; o padrão é o mesmo Gemini do `.env.example`.
4. **Sem dependência nova.** O agente usa só a biblioteca padrão do Python, como o resto do backend
   (ADR 0010).
5. **Controles contra a "tríade letal"** (dados privados, conteúdo não confiável e comunicação externa):
   - PR de fork não roda os jobs de IA (sem segredo e sem token de escrita); nada usa `pull_request_target`.
   - Logs, diff e alertas vão ao LLM entre marcadores de dado não confiável, com instrução para ignorar
     ordens dentro deles. A resposta só vira comentário, issue ou resumo do job: o agente não executa
     código, não altera arquivos e não tem ferramenta.
   - Padrões de segredo (chaves `sk-`, `AIza`, tokens do GitHub, JWT, `Bearer`, `*_KEY=`) são mascarados
     antes do envio. Os dados dos cenários de incidente são fictícios.
   - Permissões mínimas por job (`contents: read` no topo; escrita só onde comenta ou abre issue).
   - Cada resposta fica num artefato (`nexus-devops-out/*.md` e `*.json`, com modelo, tokens e hash do prompt)
     por 30 dias, para auditoria.
6. **Validação por falha controlada.** `scripts/nexus_devops/injetar_falha.py` introduz erros conhecidos
   (tipo, lógica, lint e isolamento) em branches descartáveis, para medir se o diagnóstico acerta.

## Consequências

- Positivas: diagnóstico da falha dentro do PR, resumo das mudanças para a documentação e análise de
  causa-raiz de alerta, com a revisão humana preservada.
- Negativas: os testes unitários rodam duas vezes nos PRs (`ci` e `nexus-devops`); custo de tokens por PR;
  um colaborador com escrita no repositório poderia alterar o agente na própria branch e ler o segredo.
  Por isso a chave é exclusiva do pipeline, com limite de gasto e rotação periódica.
- `workflow_run`, `repository_dispatch` e `workflow_dispatch` só funcionam depois que o workflow chega à
  `main`; antes disso, só os jobs de PR rodam.
- Para desligar: apagar o workflow e o segredo. Nada no produto depende dele.
