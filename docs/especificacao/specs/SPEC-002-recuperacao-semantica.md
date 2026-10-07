# Spec: Recuperação Semântica

**ID**: SPEC-20261007-002
**Status**: Rascunho
**Autor**: Cleiton Medeiros (elaborada com apoio de IA generativa, pendente de revisão)
**Data**: 2026-10-07
**Fase**: 2 de 6 — etapa 10 do [plano incremental](../../plano-incremental.md)
**Depende de**: SPEC-20261007-001

## Contexto e Problema

A ADR 0004 determina embeddings locais com o modelo
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, mas o código utiliza
`LocalHashEmbeddingGateway`, que distribui o hash de cada palavra em 384 posições. Esse vetor só
aproxima textos que compartilham palavras idênticas: sinônimos, paráfrases e perguntas em
linguagem natural não encontram o trecho correto.

O chunking corta o texto a cada 700 caracteres, com 120 de sobreposição, sem considerar frases,
títulos ou tabelas, e não guarda seção nem página — o que impede citar a origem.

Esta fase implementa de fato a ADR 0004, introduz chunking estrutural e cria a rotina de
reindexação exigida pela própria ADR.

## Requisitos Funcionais

- [ ] RF-28: embeddings com modelo semântico multilíngue local.
- [ ] RF-29: chunking estrutural com tamanho em tokens.
- [ ] RF-30: metadados de seção, página e modelo em cada chunk.
- [ ] RF-31: reindexação sem indisponibilidade.
- [ ] RF-32: registro do modelo e da versão do pipeline por documento.

## Requisitos Não Funcionais

- [ ] RNF-18: reindexação sem interromper consultas.
- [ ] RNF-19: recall@5 mínimo de 0,80 no assistente piloto.
- [ ] RNF-26: vetorização executada localmente.
- [ ] RNF-31: alterações de esquema por migração versionada.
- [ ] RNF-32: modelos mantidos em volume de cache.

## Regras de Negócio

- RN-16: troca de modelo exige reindexação completa antes de servir consultas.
- RN-14: a mudança só é aceita com avaliação registrada.

## Critérios de Aceite (Gherkin)

```gherkin
Funcionalidade: Recuperação semântica

  Cenário: Encontrar trecho por paráfrase
    Dado um documento indexado com a frase "o reembolso é feito em até 10 dias úteis"
    Quando o usuário pergunta "quanto tempo demora para devolverem meu dinheiro?"
    Então o trecho sobre reembolso está entre os cinco primeiros recuperados

  Cenário: Vetorização sem acesso externo
    Dado que o container do backend está sem acesso à internet
    E o modelo de embedding está no volume de cache
    Quando um documento é ingerido
    Então os vetores são gerados com 384 dimensões
    E nenhuma chamada de rede externa é realizada

  Cenário: Chunk respeita a estrutura
    Dado um documento com títulos, parágrafos e uma tabela
    Quando o documento é fragmentado
    Então nenhum chunk termina no meio de uma frase
    E as linhas da tabela permanecem junto do cabeçalho
    E cada chunk registra o título da seção e a página de origem
    E nenhum chunk excede o limite de tokens configurado

  Cenário: Reindexar sem indisponibilidade
    Dado um assistente com base indexada e consultas em andamento
    Quando o administrador solicita a reindexação
    Então as consultas continuam sendo atendidas pela collection vigente
    E ao final o alias aponta para a nova collection
    E a collection anterior é removida

  Cenário: Falha na reindexação
    Dado uma reindexação em andamento
    Quando o processamento de um documento falha
    Então o alias permanece na collection vigente
    E a collection parcial é descartada

  Cenário: Meta de qualidade
    Dado o conjunto de referência do assistente piloto
    Quando a avaliação é executada após a reindexação
    Então o recall@5 é igual ou superior a 0,80
```

## Design da Solução

### Embeddings

| Item | Definição |
|------|-----------|
| Adaptador | `SentenceTransformerEmbeddingGateway`, implementando o `EmbeddingGateway` existente |
| Modelo | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (ADR 0004), lido de `EMBEDDING_MODEL_NAME` |
| Dimensão | 384, lida de `EMBEDDING_VECTOR_SIZE` e conferida com o modelo na inicialização |
| Execução | CPU, dentro dos containers `backend` e `worker`; modelo carregado uma única vez por processo |
| Cache | Volume `backend_cache` montado no diretório de modelos |
| Testes | `LocalHashEmbeddingGateway` permanece apenas como dublê em testes unitários |

A porta `EmbeddingGateway` ganha a distinção entre vetorizar documentos e vetorizar consultas
(`embed_documents` e `embed_query`), para acomodar modelos que usam prefixos diferentes sem
alterar os casos de uso novamente.

### Chunking

- Nova porta de domínio `DocumentChunker`, que recebe o documento extraído (blocos com tipo,
  texto, seção e página) e devolve chunks com metadados.
- Implementação `StructuralDocumentChunker` na infraestrutura:
  1. agrupa blocos por seção, seguindo a hierarquia de títulos;
  2. mantém parágrafos, itens de lista e tabelas inteiros sempre que couberem;
  3. divide blocos maiores que o limite em fronteiras de frase;
  4. aplica sobreposição de frases entre chunks consecutivos da mesma seção;
  5. prefixa cada chunk com o caminho de títulos da seção.
- O tamanho é medido com o tokenizador do próprio modelo de embedding.
- A extração de texto passa a devolver blocos estruturados em vez de uma única string.

**Atenção ao limite do modelo:** o modelo definido na ADR 0004 trunca entradas longas (limite de
sequência de 128 tokens, a confirmar na implementação). O conteúdo além do limite não influencia
o vetor. Por isso `CHUNK_MAX_TOKENS` não pode ultrapassar o limite do modelo carregado, e o
adaptador deve recusar a configuração que o exceda. O corte atual de 700 caracteres já ultrapassa
esse limite em parte dos casos.

### Metadados por chunk

Aos campos do MVP (`assistant_id`, `document_id`, `chunk_index`, `source_name`, `content_hash`,
`text`) somam-se:

| Campo | Descrição |
|-------|-----------|
| `section_path` | Caminho de títulos da seção, por exemplo `Política de Férias > Estagiários` |
| `page` | Página de origem, quando o formato a fornece |
| `embedding_model` | Nome do modelo que gerou o vetor |
| `pipeline_version` | Versão do pipeline de ingestão |

### Reindexação

- Collections passam a ser versionadas: `assistant-{assistant_id}-v{n}`.
- O nome lógico `assistant-{assistant_id}` torna-se um **alias** do Qdrant apontando para a versão vigente.
- Caso de uso `ReindexAssistantUseCase`: cria a versão seguinte, reprocessa os documentos,
  confere as contagens, troca o alias de forma atômica e remove a versão anterior.
- `VectorStoreGateway` ganha operações de alias (`point_alias`, `resolve_alias`).
- **Migração inicial:** as collections do MVP chamam-se `assistant-{assistant_id}`, o mesmo nome
  do futuro alias. A migração cria `-v2` com os novos vetores, remove a collection antiga e só
  então cria o alias; nesse intervalo o assistente fica indisponível, o que é aceitável uma única
  vez em ambiente local.
- Como os arquivos originais só passam a ser armazenados na Fase 5, a reindexação desta fase exige
  **novo upload** dos documentos existentes.

### Modelo de dados

Tabela `documents` recebe `embedding_model`, `pipeline_version` e `chunk_count`. A alteração é
feita por migração versionada (ADR 0011), substituindo o `create_all` executado na subida da API.

### API

| Rota | Papel exigido a partir da Fase 4 | Descrição |
|------|----------------------------------|-----------|
| `POST /assistants/{id}/reindex` | administrador | Inicia a reindexação |
| `GET /assistants/{id}/index-status` | administrador, curador | Informa modelo, versão do pipeline e se a base está desatualizada |

## Impacto Arquitetural

- Domínio: nova porta `DocumentChunker`; `EmbeddingGateway` e `VectorStoreGateway` estendidas;
  `VectorChunk` com novos campos.
- Aplicação: `IngestDocumentUseCase` deixa de conter o algoritmo de chunking; novo
  `ReindexAssistantUseCase`.
- Infraestrutura: novos adaptadores de embedding e chunking; Qdrant com alias.
- Docker: imagem do backend passa a incluir `sentence-transformers` e PyTorch (CPU); novo volume
  `backend_cache`.
- ADRs: [0006](../../arquitetura/adrs/0006-embeddings-reais-e-reindexacao.md) (complementa a 0004)
  e [0011](../../arquitetura/adrs/0011-migracoes-versionadas-de-banco.md).

## Estratégia de Testes

- Unitários: CT-06, CT-07, CT-08, CT-09.
- Integração: CT-10, CT-11, CT-12.
- Avaliação: CT-13, comparando com a linha de base da SPEC-001.

## Riscos e Dependências

- Limite de sequência do modelo restringe o tamanho do chunk (risco R11).
- Reindexação exige novo upload dos documentos atuais (risco R9).
- Imagem maior e uso de memória mais alto no ambiente local (risco R17).
- Latência de vetorização em CPU durante a ingestão (risco R10).

## Decisões Pendentes

| Decisão | Opções | Impacto |
|---------|--------|---------|
| Valor de `CHUNK_MAX_TOKENS` e da sobreposição | Até o limite do modelo; sobreposição de uma ou duas frases | Granularidade do contexto e número de chunks |
| Extração estruturada de PDF | Manter `pypdf` com heurísticas; adotar biblioteca de layout | Qualidade de seções e tabelas; tamanho da imagem |
| Manter o modelo da ADR 0004 se a meta de recall não for atingida | Ajustar chunking; propor revisão da ADR com base na avaliação | Exige nova decisão registrada antes de trocar o modelo |
