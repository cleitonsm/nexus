# ADR 0004: Embeddings Locais sem Chamada à LLM

## Status

Aceita.

## Contexto

Embeddings serão gerados em volume durante ingestão e reprocessamento de documentos. Usar APIs
externas desde o início aumenta custo, latência e dependência operacional.

## Decisão

Gerar embeddings localmente, por exemplo com `sentence-transformers`, sem chamar uma LLM para
essa etapa.

## Consequências

- O ambiente Docker deve incluir o runtime necessário para embeddings.
- O tamanho do modelo precisa equilibrar qualidade e custo local.
- A dimensão dos vetores deve ser compatível com as collections do Qdrant.
- O provedor de LLM continua separado e usado apenas na geração de respostas.
