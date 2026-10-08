# Observabilidade

SPEC-006 (RF-56, RF-57, RNF-25, RNF-29) e decisões D1 e D2: rastreamento por etapa, métricas em
`/metrics` e um perfil opcional do Compose para visualizar. Sem SDK do OpenTelemetry nem
`prometheus-client`: a implementação é própria, só com a biblioteca padrão.

## Como ligar

```bash
# .env
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318

docker compose --profile observabilidade up -d
```

- Jaeger: `http://localhost:16686` (serviço `nexus-backend`).
- Prometheus: `http://localhost:9090`.
- Grafana: `http://localhost:3000` (`admin`/`admin` no desenvolvimento), painel **Nexus — Operação**.

Sem o perfil, nada muda no ambiente padrão: o backend continua gerando as métricas, e os
rastreamentos não são enviados.

## Rastreamento

| Trecho | Onde | Atributos |
|--------|------|-----------|
| `http.request` | toda requisição, exceto `/health` e `/metrics` | método, rota (modelo, sem ids), status |
| `chat.turn` | uma pergunta (rota normal ou streaming) | modo, ids da conversa e do assistente |
| `chat.<nó>` | cada nó do grafo: `load_conversation_history`, `persist_user_message`, `rewrite_question`, `retrieve_context`, `rerank_context`, `evaluate_context`, `build_context`, `generate_answer`, `validate_citations`, `fallback_answer`, `persist_assistant_message` | nome do nó |
| `llm.chat_completion` | cada chamada ao LLM | modelo, streaming, trechos, mensagens de histórico, tokens |
| `qdrant.hybrid_search` | cada busca | limite, resultados |
| `keycloak.verify_access` | validação do token | provedor |

- **Identificador (RNF-29):** quando o `X-Request-ID` tem 32 dígitos hexadecimais, ele é o próprio
  identificador do rastreamento; caso contrário vai no atributo `nexus.request_id`. Os logs JSON
  trazem o mesmo `request_id`.
- **Sem conteúdo (RNF-25):** atributos cujo nome contém `prompt`, `question`, `answer`, `text`,
  `content`, `excerpt`, `comment`, `token`, `key`, `secret`, `password`, `authorization` ou
  `credential` são descartados antes de sair do processo; textos são cortados em 120 caracteres;
  erros guardam só o tipo.
- **Exportação:** lotes a cada 2 s por uma thread; coletor fora do ar não atrasa a requisição (os
  trechos são descartados e contados).

## Métricas (`/metrics`)

| Métrica | Tipo | Rótulos |
|---------|------|---------|
| `nexus_http_requests_total`, `nexus_http_request_duration_seconds` | contador, histograma | método, rota, status |
| `nexus_stage_duration_seconds` | histograma | `stage` (nome do trecho) |
| `nexus_chat_questions_total` | contador | `mode` (`sync`/`stream`), `outcome` (`answered`, `fallback`, `failed`, `cancelled`) |
| `nexus_chat_time_to_first_token_seconds` | histograma | — (RNF-01) |
| `nexus_llm_tokens_total` | contador | `model`, `direction` (`input`/`output`) |
| `nexus_llm_estimated_cost_total` | contador | `model`, `currency` |
| `nexus_prompt_injection_suspected_total` | contador | — (RF-60) |
| `nexus_usage_limit_blocked_total` | contador | `window` (RN-32) |
| `nexus_feedback_total` | contador | `rating` (RF-61) |
| `nexus_ingestion_jobs` | gauge | `status` (lido do banco a cada coleta) |

`/metrics` não exige token e não passa pelo proxy do frontend (`/api/metrics` responde 404). No
ambiente local continua acessível pela porta publicada do backend (`8000`); em produção, não
publique essa porta.

Cada processo (API e worker) tem seu próprio registro em memória; o worker não expõe `/metrics`, e
os jobs de ingestão são contados pela API a partir do banco. As métricas zeram quando o contêiner
reinicia.

## Consumo e custo

Cada pergunta grava uma linha em `usage_records` (usuário, nome, conversa, assistente, modelo,
tokens, custo estimado, fallback, falha), sem texto algum. O administrador consulta em
**Consumo e limites** (`GET /admin/usage`). O custo usa `LLM_PRICE_*` vigentes no momento da
pergunta; é uma estimativa.

## Risco

O perfil consome memória extra (risco R17): Jaeger em memória limitada a 20 mil rastreamentos e
Prometheus com retenção de 7 dias.
