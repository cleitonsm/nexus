# Nexus DevOps: CI/CD assistido por GenAI

Decisão e controles: [ADR 0015](../arquitetura/adrs/0015-genai-no-pipeline-de-ci-cd.md).

## Problema

- Pipeline vermelho só diz "falhou": quem abriu o PR lê o log inteiro para achar a causa e ligá-la ao
  código alterado.
- PR verde chega sem resumo das mudanças, e a documentação fica para trás.
- Alerta de produção exige cruzar métricas, logs e commits recentes antes de agir.

## Solução

| Etapa | Job | O que faz |
|---|---|---|
| Gatilho | — | Pull request para `main` |
| Build | `lint` | ruff (`F,E9`) e `compileall` |
| Teste | `unit_test` | Suíte `backend/tests/unit`; guarda o log como artefato se falhar |
| IA na falha | `ai_debugger` (`if: failure()`) | Lê o log dos jobs que falharam pela API do GitHub, cruza com o diff e comenta no PR: diagnóstico, causa-raiz, trecho do log, correção, riscos de segurança e confiança |
| IA no sucesso | `ai_change_summary` (`if: success()`) | Resume o diff num comentário fixo (e, opcional, na descrição do PR) |
| Implantação | `deploy_staging` | Após o `ci` verde num push para a `main`: build das imagens, smoke test e, opcional, push para o GHCR |
| Monitoramento | `ai_incident` | Alerta via `repository_dispatch` (ou cenário fictício) vira issue com os rótulos `incidente` e `nexus-devops` e análise de causa-raiz |

O agente é `scripts/nexus_devops/analista.py` (só biblioteca padrão). Ele nunca reprova o pipeline.

## Configuração

Em **Settings → Secrets and variables → Actions**:

| Tipo | Nome | Valor |
|---|---|---|
| Secret | `GENAI_API_KEY` | Chave exclusiva do pipeline, com limite de gasto no provedor |
| Variable (opcional) | `GENAI_API_URL` | Endpoint `/chat/completions`; vazio = Gemini compatível com OpenAI |
| Variable (opcional) | `GENAI_MODEL` | Modelo; vazio = `gemini-3.8-flash` |
| Variable (opcional) | `GENAI_RESUMO_NA_DESCRICAO` | `true` para gravar o resumo também na descrição do PR |
| Variable (opcional) | `GENAI_PUBLICAR_IMAGENS` | `true` para publicar as imagens de staging no GHCR |

Para OpenAI: `GENAI_API_URL=https://api.openai.com/v1/chat/completions` e `GENAI_MODEL=gpt-4o-mini`.
Sem o segredo, os jobs de IA rodam e só avisam que a análise está desligada.

Crie também o ambiente `staging` em **Settings → Environments** (pode exigir aprovação manual antes do
deploy).

Os jobs de PR funcionam já no PR que adiciona o workflow. O deploy (`workflow_run`) e os alertas
(`repository_dispatch`, `workflow_dispatch`) só disparam depois que o arquivo está na branch padrão.

## Validação com falha controlada

```bash
git switch main && git pull
git switch -c chaos/falha-tipo
python scripts/nexus_devops/injetar_falha.py tipo
git commit -am "chaos: falha controlada (tipo)"
git push -u origin HEAD
gh pr create --base main --title "chaos: falha controlada (tipo)" --body "Falha controlada. Nao fazer merge."
```

| Cenário | Onde | Estágio que falha | O que a IA deve explicar |
|---|---|---|---|
| `tipo` | `domain/usage.py` | `unit_test` | `TypeError` de `Decimal / str`; correção `Decimal(1000)` |
| `logica` | `domain/usage.py` | `unit_test` | custo 10x maior: divisor 100 em vez de 1000 |
| `lint` | `domain/usage.py` | `lint` (testes nem rodam) | `F401`, import sem uso |
| `isolamento` | `domain/access.py` | `unit_test` | interseção virou união no filtro de grupos: **risco de vazamento entre grupos** |

O que observar no PR:

1. `unit_test` (ou `lint`) fica vermelho.
2. `ai_debugger` inicia em seguida e fica verde.
3. Aparece o comentário **🤖 Nexus DevOps comentou**, marcando o autor. Novos pushes atualizam o mesmo
   comentário.

Corrija com `python scripts/nexus_devops/injetar_falha.py tipo --reverter`, faça commit e push: o pipeline
fica verde e `ai_change_summary` publica o resumo. Feche o PR sem merge e apague a branch.

## Implantação e alertas

- **Deploy:** um merge na `main` faz o `ci` rodar; com ele verde, `deploy_staging` constrói
  `nexus-backend` e `nexus-frontend`, roda o smoke test e, se habilitado, publica `:staging` no GHCR.
- **Alerta fictício pela interface:** Actions → `nexus-devops` → Run workflow → escolha o cenário
  (`ttft-alto`, `fila-ingestao`, `injecao-prompt`).
- **Alerta por webhook** (o que o Grafana/Alertmanager faria, através de um relay que monte este corpo):

```bash
jq -n --slurpfile p scripts/nexus_devops/cenarios/ttft-alto.json \
  '{event_type: "alerta-observabilidade", client_payload: $p[0]}' \
  | gh api repos/cleitonsm/nexus/dispatches --input -
```

O `client_payload` aceita no máximo 10 chaves no primeiro nível. O job `ai_incident` abre uma issue
`[incidente] <alerta>` com severidade sugerida, hipóteses de causa-raiz com evidência, correlação com os
commits recentes, próximos passos (PromQL, `docker compose logs`, SQL somente leitura) e mitigação.

## Como medir o resultado

Por cenário, registre: a IA acertou a causa-raiz? A correção sugerida compila e passa nos testes? Ela
apontou o risco de segurança do cenário `isolamento`? Quanto tempo levou do vermelho ao comentário?
Quantos tokens custou (artefato `nexus-devops-*`, arquivo `.json`)? Houve alucinação (arquivo ou linha
inexistente)?

## Segurança e limites

- PR de fork não executa a IA. O agente não tem ferramentas: só lê log, diff e alerta e escreve texto.
- Segredos são mascarados antes do envio ao LLM; ainda assim, nunca coloque dado real nos cenários.
- Quem tem escrita no repositório pode alterar o agente na própria branch, então limite o gasto da chave e
  troque-a periodicamente.
- Os testes unitários rodam no `ci` e no `nexus-devops` em cada PR, o que dobra esse custo de minutos.
- Testes do próprio agente: `backend/tests/unit/test_nexus_devops.py` (LLM e GitHub falsos, sem rede).
