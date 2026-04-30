# ADR 0004: Embeddings Locais sem Chamada à LLM

## Status

Aceita.

## Contexto

Embeddings serão gerados em volume durante ingestão e reprocessamento de documentos. Usar APIs
externas desde o início aumenta custo, latência e dependência operacional.

## Decisão

Gerar embeddings localmente, por exemplo com `sentence-transformers`, sem chamar uma LLM para
essa etapa.

### Modelo Inicial Recomendado

- **Modelo**: `sentence-transformers/all-MiniLM-L6-v2`.
- **Dimensão do vetor**: 384.
- **Justificativa**:
  - equilíbrio entre qualidade semântica e baixo custo computacional local;
  - tempo de inferência adequado para ingestão incremental no MVP;
  - ampla adoção e documentação, reduzindo risco técnico inicial.

### Diretriz de Configuração

- O dimensionamento da collection no Qdrant deve iniciar em `384`.
- A troca de modelo deve ser parametrizável por variável de ambiente.
- Ao trocar modelo, deve existir rotina explícita de reindexação das collections afetadas.

## Consequências

- O ambiente Docker deve incluir o runtime necessário para embeddings.
- O tamanho do modelo precisa equilibrar qualidade e custo local.
- A dimensão dos vetores deve ser compatível com as collections do Qdrant.
- O provedor de LLM continua separado e usado apenas na geração de respostas.
