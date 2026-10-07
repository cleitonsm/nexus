# ADR 0010: Observabilidade e Avaliação Contínua de Qualidade

## Status

Aceita em 2026-10-07, com a aprovação da SPEC-001. Parcialmente implementada: os itens 1, 2 e 5
da decisão estão no código, e o item 8 é aplicado aos logs. O item 3 depende da execução no
ambiente Docker. Os itens 4, 6, 7 e 9 pertencem à Fase 6.

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
