# ADR 0010: Observabilidade e Avaliação Contínua de Qualidade

## Status

Aceita em 2026-10-07, com a aprovação da SPEC-001. Itens 1, 2, 5, 6, 7, 8 e 9 no código (os
quatro últimos na Fase 6, em 2026-10-08). O item 3 depende da execução no ambiente Docker. O item
4 foi ajustado pela decisão D4 da SPEC-006 (ver abaixo).

### Ajustes da SPEC-006 (2026-10-08)

- **Item 4 (D4):** a integração contínua do GitHub roda os testes unitários e as verificações
  estáticas; a avaliação de qualidade roda por script local (`scripts/quality-gate.sh`), com o
  mesmo critério de regressão, para que nenhuma API key vire segredo no GitHub.
- **Item 6 (D2):** "OpenTelemetry" significa o formato e o protocolo (OTLP/HTTP em JSON), não o
  SDK. O rastreamento e as métricas são implementação própria, só com a biblioteca padrão, atrás
  das portas `Tracer` e `MetricsRecorder` do domínio. Detalhes em
  [observabilidade.md](../../infraestrutura/observabilidade.md).
- **Item 9 (D1):** Jaeger, Prometheus e Grafana no perfil `observabilidade` do Compose.

## Contexto

O MVP não mede a qualidade das respostas e não oferece visibilidade sobre o que acontece em cada
requisição. O único registro é um arquivo de depuração gravado dentro do container. Sem medida,
não é possível comprovar o ganho de nenhuma das mudanças planejadas nem detectar regressões.

## Decisão

1. Manter um conjunto de referência por assistente, versionado no repositório e validado por curador.
2. Medir recall@k, MRR, fidelidade e taxa de fallback correto por um caso de uso de avaliação que
   reutiliza as mesmas portas do chat.
3. Registrar a linha de base do pipeline atual antes de qualquer mudança.
4. Executar a avaliação na integração contínua e bloquear regressões acima da tolerância.
5. Emitir logs estruturados em JSON com identificador de requisição.
6. Instrumentar com OpenTelemetry, com um span por nó do grafo conversacional, e expor métricas.
7. Registrar consumo de tokens e custo estimado por conversa.
8. Nunca registrar segredos, tokens ou conteúdo integral de documentos em logs, spans ou métricas.
9. Oferecer as ferramentas de visualização como perfil opcional do Docker Compose.

## Consequências

- Toda fase da evolução passa a ter um critério objetivo de aceite.
- O conjunto de referência depende de curadoria humana contínua.
- A métrica de fidelidade usa LLM como juiz, com custo e variabilidade próprios.
- O ambiente padrão permanece leve; a observabilidade completa é ativada sob demanda.
- Os arquivos `debug-a1f259.log` e `debug-8fd7a3.log` e o código que os gravava foram removidos.

## Alternativas Consideradas

- **Avaliação apenas manual:** descartada por não ser repetível nem comparável entre versões.
- **Plataforma externa de observabilidade de LLM:** descartada por enviar perguntas e trechos de
  documentos para fora do ambiente.
- **Somente logs, sem rastreamento:** insuficiente para localizar a etapa lenta de uma resposta.
