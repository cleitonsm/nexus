# Plano de Implementação — SPEC-003 Busca Híbrida, Reranking e Citações

**Spec**: [SPEC-20261007-003](SPEC-003-busca-hibrida-reranking-citacoes.md) (Aprovada em 2026-10-07)
**Status do plano**: Código de P1 a P8 entregue em 2026-10-07; P9 e a validação no Docker pendentes
**Data**: 2026-10-07
**Elaborado com apoio de IA generativa, pendente de revisão do autor**

## 0. Andamento

| Pacote | Situação em 2026-10-07 | Verificado por |
|--------|------------------------|----------------|
| P1 Domínio | Entregue: `SparseVector`, `SparseEmbeddingGateway`, `RerankerGateway`, `ContextChunk`, `Citation`, `hybrid_search`, citações em `ChatMessage` | Testes unitários |
| P2 BM25 local | Entregue: `Bm25SparseEmbeddingGateway`, em Python puro | Testes unitários |
| P3 Qdrant híbrido | Código entregue: vetores nomeados `dense` e `sparse` (IDF), Query API com duas pré-buscas e fusão RRF, filtro de payload | Nada: `qdrant-client` não estava disponível fora do Docker |
| P4 Reranking | Código entregue: `CrossEncoderRerankerGateway` | Nada: o modelo não pôde ser carregado fora do Docker |
| P5 Serviços de aplicação | Entregue: `ContextRetriever`, `GroundedAnswerGenerator`, `trim_history`, `fit_context`, `RetrievalSettings` | Testes unitários |
| P6 Grafo do chat | Entregue: reescrita, busca híbrida, reranking, nota mínima, orçamento, geração, validação das citações | Testes unitários, com o LangGraph substituído por um dublê local |
| P7 Persistência e API | Código entregue: migração `0003_message_citations`, repositório, `citations` e `rewritten_query` no chat, citações em `GET /conversations/{id}`, 409 para base desatualizada | Nada: FastAPI, SQLAlchemy e Alembic não estavam disponíveis |
| P8 Frontend | Código entregue: tipo `Citation`, seletor por mensagem, lista de fontes e painel do trecho no chat | Apenas verificação de sintaxe e do seletor isolado; `npm` estava bloqueado, sem build e sem Vitest |
| P9 Avaliação e calibração | Não iniciado: depende do ambiente Docker | — |

Verificação feita: 265 testes unitários passam, fora do Docker, em Python 3.13, com o LangGraph
substituído por um dublê local.

**Não verificado**: o adaptador Qdrant, o reranker, a migração, o repositório, as rotas, o comando
de avaliação, a construção da imagem, todos os testes de integração e todo o frontend. Esse código
só passou por verificação de sintaxe. A Fase 2 tampouco foi validada no Docker, então a primeira
execução vai revelar ajustes das duas fases juntas.

## 0.1 Como validar no Docker

1. Concluir antes o roteiro da Fase 2 que ainda couber (em especial a linha de base do MVP no
   commit `9dcf007`, que só pode ser gerada lá).
2. `docker compose up -d --build`. A subida aplica a migração `0003_message_citations`.
3. Testes no container:
   `docker compose run --rm --no-deps -v ./backend/tests:/app/tests backend python -m unittest discover -s tests/unit`
   e o mesmo com `-s tests/integration` (sem `--no-deps`, para ter Qdrant e PostgreSQL). O primeiro
   uso baixa o reranker (algumas centenas de MB) para o volume `backend_cache`.
4. Frontend: `npm ci && npm test && npm run build` em `frontend/`.
5. **Reindexar todo assistente que já tenha documentos**: `POST /assistants/{id}/reindex`. As
   collections da Fase 2 não têm o vetor esparso; até a reindexação, o upload responde 409 e o
   chat funciona só com a busca densa.
6. Avaliação do piloto: `scripts\eval.ps1 nexus-docs` (CT-22: fidelidade ≥ 0,90 e fallback correto
   ≥ 90%). O comando reconstrói a base do piloto por causa da nova versão do pipeline.
7. Conferir nos logs `chat.retrieval.finished` e `chat.rerank.finished` (`duration_ms`) contra o
   RNF-16 (3 segundos para 95% das perguntas).
8. Validação manual do chat: resposta com fontes, clique na fonte, pergunta de continuação,
   pergunta fora do escopo.

## 1. Decisões

Registradas por Cleiton Medeiros em 2026-10-07.

| # | Decisão | Escolha |
|---|---------|---------|
| D1 | Aprovação da SPEC-003 e da ADR 0007 | Aprovadas; implementar sobre a Fase 2 ainda não validada |
| D2 | Formato da citação | Marcadores `[n]` |
| D3 | Modelo de reranking | `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` |
| D4 | Parâmetros iniciais | 30 candidatos, 5 trechos, nota mínima 0,5, contexto 2000 tokens, histórico 1500 tokens |

Ainda em aberto:

| # | Decisão | Observação |
|---|---------|------------|
| D5 | Calibração de D4 | Só diante do resultado do CT-22. A nota mínima 0,5 é provisória: é o ponto neutro da sigmoide, não um valor medido. |

## 2. Comportamentos revisados pelo autor

Revisados por Cleiton Medeiros em 2026-10-07. Os cinco primeiros foram alterados na revisão; os
três seguintes foram mantidos como implementados.

| # | Comportamento | Decisão |
|---|---------------|---------|
| D6 | Marcador que aponta para trecho inexistente | **Alterado**: a resposta é aceita se houver ao menos um marcador válido e os inválidos são removidos do texto (em `[1, 7]` fica `[1]`). Risco aceito: um número entre colchetes que não era citação, como `[2024]`, também é removido. |
| D7 | Falha do LLM na reescrita | **Alterado**: a busca segue com a pergunta original e o log registra `chat.rewrite.failed`. Uma pergunta fora do escopo recebe o fallback mesmo com o LLM indisponível. |
| D8 | Base anterior à busca híbrida | **Alterado**: o chat consulta a collection só pelo vetor denso (log `vector_store.legacy_dense_search`) até a reindexação; termos exatos continuam falhando até lá. O 409 fica restrito à base incompatível com o modelo de embedding atual. O upload continua recusado. |
| D9 | `top_k` do `POST /chat` | **Alterado**: teto por pergunta, nunca acima de `RERANK_TOP_N`. O frontend envia `top_k: 4` fixo, então o chat usa 4 trechos enquanto `RERANK_TOP_N` for 5; a avaliação usa `RERANK_TOP_N`. |
| D10 | Parâmetros do BM25 | **Alterado**: `BM25_K1`, `BM25_B` e `BM25_AVG_LENGTH` no ambiente. Mudar exige reindexar e nada detecta a diferença. |
| D11 | Fontes devolvidas | Mantido: apenas os trechos citados. |
| D12 | Medida dos orçamentos | Mantido: tokenizador do modelo de embedding, por aproximação. |
| D13 | Janela de histórico | Mantido: mensagens recentes contíguas; a janela não pula uma mensagem grande. |

## 2.1 Outros comportamentos definidos na implementação

- **Campo `number` na citação**: a spec lista os campos de `Citation` sem o número; ele foi
  incluído porque é o que liga o `[n]` do texto à fonte exibida.
- **Histórico**: o mesmo histórico limitado vai para a reescrita e para a geração. A truncagem é
  feita no nó que carrega o histórico, não no de montagem do contexto.
- **Contexto**: trechos na ordem do reranking até esgotar o orçamento; se nem o primeiro couber, a
  resposta é o fallback.
- **Reescrita**: o resultado vazio mantém a pergunta original. A geração e a mensagem gravada usam
  sempre a pergunta original; a reescrita serve só à busca e ao reranking.
- **Pergunta fora do escopo em conversa com histórico**: o LLM de geração não é chamado, mas a
  chamada de reescrita acontece antes da busca.
- **Assistente sem collection**: a busca devolve lista vazia e a resposta é o fallback.
- **BM25**: lista curta de palavras vazias do português; sem radicalização.
- **Avaliação**: recall@k e MRR passam a ser medidos depois do reranking; a opção
  `--context-top-k` do comando foi removida.
- **Delimitação dos trechos**: no prompt, cada trecho vai em um bloco `<trecho numero=...>` com
  documento, seção e página, e o texto do documento não consegue fechar o bloco.

## 3. Lacunas e conflitos encontrados

- **L1 — Variáveis da Fase 2 com nomes divergentes.** O `.env.example` e a documentação usam
  `UPLOAD_MAX_BYTES` e `DOCUMENTS_STORAGE_PATH`; `infrastructure/composition.py` lê
  `DOCUMENT_MAX_FILE_BYTES` e `DOCUMENTS_DIR`. Como os padrões coincidem, nada falha hoje, mas
  alterar o `.env` não tem efeito. Não corrigido: está fora do escopo desta fase.
- **L2 — Código de depuração no frontend.** `chat-page.component.ts`, `nexus.effects.ts` e
  `nexus-api.service.ts` enviam dados para `http://127.0.0.1:7657/ingest/...` (blocos
  `#region agent log`). Já existiam; não foram alterados.
- **L3 — Respostas renderizadas como HTML.** O `MarkdownPipe` usa `bypassSecurityTrustHtml` sobre
  o texto do LLM. Os trechos citados são exibidos como texto puro, sem passar pelo pipe.
- **L4 — `qdrant-client` sem versão fixa** (herdada da Fase 2). A Query API com pré-buscas e o
  modificador IDF exigem cliente e servidor 1.10 ou superior; o servidor é 1.11.3.
- **L5 — Primeira pergunta lenta.** O reranker é carregado na primeira pergunta de cada processo.
- **L6 — Skill `desenvolvedor-nexus`** ainda descreve o embedding por hash, a busca densa e
  `assistant_{assistant_id}`.

## 4. Requisitos atendidos pelo código entregue

| Requisito | Onde |
|-----------|------|
| RF-33 | `Bm25SparseEmbeddingGateway`, `QdrantVectorStoreGateway.hybrid_search`, `ContextRetriever.search` |
| RF-34 | `CrossEncoderRerankerGateway`, `ContextRetriever.rerank` |
| RF-35, RN-17 | `ContextRetriever.select_relevant`, nó `evaluate_context` |
| RF-36 | `GroundedAnswerGenerator.rewrite_question`, nó `rewrite_question` |
| RF-37, RN-18 | `resolve_citations`, nó `validate_citations`, coluna `messages.citations`, `ChatResponse.citations` |
| RF-38, RNF-33 | `selectCurrentCitationsByMessage`, lista de fontes e painel em `chat-page.component.html` |
| RF-39, RN-19 | `trim_history`, `fit_context` |
| RNF-26 | BM25 e reranker executados no processo da API |
| RNF-16, RNF-20, RNF-21 | A medir no Docker (logs de duração e CT-22) |
