# Fluxo Conversacional com LangGraph

## Objetivo

Modelar a conversa RAG como um fluxo explícito e testável. O LangGraph deve coordenar etapas,
mas a aplicação continua responsável por iniciar casos de uso e persistir resultados.

## Fluxo Inicial

```mermaid
flowchart TD
    Start[Mensagem do usuario] --> Retrieve[Recuperar contexto]
    Retrieve --> Evaluate[Avaliar relevancia]
    Evaluate -->|contexto suficiente| Generate[Gerar resposta]
    Evaluate -->|contexto insuficiente| Fallback[Responder limite de conhecimento]
    Generate --> Persist[Persistir mensagens]
    Fallback --> Persist
    Persist --> End[Fim]
```

## Etapas

- **Recuperar contexto**: consulta a collection do assistente ativo no Qdrant.
- **Avaliar relevância**: decide se os trechos recuperados são suficientes para responder.
- **Gerar resposta**: chama o provedor de LLM com pergunta, histórico e contexto.
- **Fallback**: informa que a base do assistente não contém evidência suficiente.
- **Persistir mensagens**: grava pergunta e resposta no histórico da conversa.

## Regra de Produto

O assistente não deve apresentar como fato uma resposta que não esteja apoiada no contexto
recuperado. Quando não houver evidência suficiente, a resposta deve ser explícita sobre a
limitação.
