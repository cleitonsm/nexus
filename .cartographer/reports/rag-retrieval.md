# Segment: rag-retrieval

**Reviewed by:** ai-pipeline-reviewer

## Files reviewed
- `backend/src/application/services/grounded_answer.py`
- `backend/src/application/services/retrieval.py`
- `backend/src/application/use_cases/chat_with_assistant.py`
- `backend/src/application/use_cases/infer_assistant.py`
- `backend/src/domain/citations.py`
- `backend/src/domain/prompt_injection.py`
- `backend/src/infrastructure/composition.py`
- `backend/src/infrastructure/embeddings/bm25_sparse_embedding.py`
- `backend/src/infrastructure/embeddings/local_embedding.py`
- `backend/src/infrastructure/embeddings/sentence_transformer_embedding.py`
- `backend/src/infrastructure/reranking/cross_encoder_reranker.py`
- `backend/src/infrastructure/vector_store/qdrant_store.py`

## Integrations
- qdrant (qdrant_client, Query API prefetch + RRF fusion, payload indexes, aliases)
- huggingface (sentence-transformers SentenceTransformer + CrossEncoder, CPU, HF_HOME cache)
- openai (OpenAI-compatible LLM via `LLMGateway` port; adapter lives outside this segment)
- langgraph (StateGraph orchestration inside application layer)

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `grounded_answer.py` | `DEFAULT_ANSWER_INSTRUCTION` / `CITATION_INSTRUCTION` / `REWRITE_INSTRUCTION` | const | Prompt templates (PT-BR) |
| `grounded_answer.py` | `GroundedAnswer` | dataclass | Accepted answer text + citations (RN-18) |
| `grounded_answer.py` | `trim_history` | function | Most recent contiguous messages within token budget |
| `grounded_answer.py` | `fit_context` | function | Numbers chunks in relevance order until budget exhausted |
| `grounded_answer.py` | `GroundedAnswerGenerator` | class | Rewrite question, generate/stream answer, validate citations |
| `grounded_answer.py` | `build_answer_instruction` / `build_answer_prompt` | function | System prompt (assistant prompt + citation rule) / user prompt |
| `retrieval.py` | `RetrievalSettings` | dataclass | candidates/top_n/min_score/context+history budgets |
| `retrieval.py` | `ContextRetriever` | class | Hybrid search, rerank, min-score selection |
| `chat_with_assistant.py` | `ChatWithAssistantInput` | dataclass | User, conversation, question, top_k, fallback text |
| `chat_with_assistant.py` | `ChatState` | TypedDict | LangGraph state for one chat turn |
| `chat_with_assistant.py` | `ChatWithAssistantUseCase` | class | SPEC-003 chat graph, sync + streaming, audit, usage |
| `chat_with_assistant.py` | `ConversationNotFoundError` | exception | Conversation missing or not owned |
| `chat_with_assistant.py` | `_retrieved` / `_turn_attributes` / `_elapsed_ms` | function | Audit/trace helpers |
| `infer_assistant.py` | `InferAssistantUseCase` | class | LLM picks an assistant id from a catalog (JSON reply) |
| `citations.py` | `ContextChunk` / `Citation` | dataclass | Numbered chunk sent to LLM / resolved source |
| `citations.py` | `cited_numbers` / `strip_unknown_markers` / `resolve_citations` | function | Parse `[n]` markers, drop invalid, map to chunks |
| `prompt_injection.py` | `detect_prompt_injection` | function | Regex flagging of injection patterns (RF-60) |
| `composition.py` | `build_embedding_gateway` / `build_token_counter` / `build_sparse_embedding_gateway` / `build_reranker_gateway` | function | lru_cached singletons for models |
| `composition.py` | `retrieval_settings` / `usage_settings` / `llm_model_name` / `bm25_parameters` | function | Env-driven settings |
| `composition.py` | `build_token_verifier` / `build_group_directory` / `cors_allowed_origins` / misc | function | Auth, CORS, storage, OCR, observability wiring |
| `bm25_sparse_embedding.py` | `tokenize` / `Bm25SparseEmbeddingGateway` | function/class | Local BM25 TF component, hashed 32-bit term indices |
| `local_embedding.py` | `LocalHashEmbeddingGateway` | class | Deterministic hash embedding test double |
| `sentence_transformer_embedding.py` | `_load_model` / `SentenceTransformerEmbeddingGateway` / `SentenceTransformerTokenCounter` | function/class | Cached ST model, dense embeddings, token counting |
| `cross_encoder_reranker.py` | `CrossEncoderRerankerGateway` | class | CPU cross-encoder, sigmoid scores 0..1 |
| `qdrant_store.py` | `QdrantVectorStoreGateway` | class | Collections, upsert, hybrid search, ACL/active payloads, aliases |
| `qdrant_store.py` | `_filter` / `_access_filter` / `_to_result` / `_payload` | function | Filter building, point mapping |

## Conventions observed
- **Naming**: snake_case functions, PascalCase classes, UPPER_SNAKE constants; PT-BR docstrings/prompts, English identifiers and log event names.
- **Error handling**: raises builtins (`ValueError`, `RuntimeError`) and domain errors (`IndexOutdatedError`, `DomainValidationError`); rewrite swallows only `ValueError/RuntimeError`; Qdrant catches only `UnexpectedResponse`.
- **Logging**: stdlib `logging`, dotted event names (`chat.rewrite.failed`) with `extra={}`; no text/PII logged (RNF-25 honoured).
- **Async style**: fully synchronous (blocking model inference, blocking Qdrant client, sync generator for streaming).
- **Type hints**: fully typed except LangGraph graph objects and `_stream_answer` return; several `type: ignore`.

## Internal duplication
- `_fold` (`bm25_sparse_embedding.py:31`) and `_normalize` (`prompt_injection.py:48`) are identical NFKD accent-fold functions.
- `_load_model` lru_cache loader pattern duplicated in `sentence_transformer_embedding.py:7` and `cross_encoder_reranker.py:10`.
- Double sort: reranker sorts (`cross_encoder_reranker.py:64`), then `ContextRetriever.rerank` sorts again (`retrieval.py:95`).
- Double top_n cut: `rerank` truncates to `limit` (`retrieval.py:100`), `select_relevant` re-slices `[:top_n]` (`retrieval.py:106`).
- Three near-identical LangGraph builds (`chat_with_assistant.py:434`, `:453`, `:466`) to support stream vs sync.
- `_to_result` uses literal `"document_id"` (`qdrant_store.py:399`) instead of the `DOCUMENT_ID` constant (`:24`).

## Cross-segment hints
- **LLM gateway (openai segment)**: `max_tokens`, `temperature`, timeout, retry/backoff and chunk delimiting (`<trecho>` tags implied by `prompt_injection.py:39`) all live in the adapter, not here. Verify: (a) `max_tokens` set; (b) chunk text escapes `</trecho>`; (c) exceptions are mapped to `ValueError/RuntimeError`, otherwise the rewrite fallback at `grounded_answer.py:124` does not catch timeouts.
- **API/DI segment**: lifetime of `ChatWithAssistantUseCase`. It holds per-request mutable state (`_ranked_so_far`, `_usage_so_far`, `chat_with_assistant.py:139-140`). Singleton = cross-user audit/usage contamination; per-request = 3 LangGraph compiles per request (`:141-143`).
- **API segment**: sync model inference + Qdrant calls must run in threadpool (`def` routes), not inside `async def` routes, or the event loop blocks.
- **API segment**: no question length cap here; `ChatWithAssistantInput.question` is unbounded (cost + rewrite prompt size).
- **Ingestion segment**: ACL is fail-open: chunks with absent/empty `allowed_groups` are visible to every assistant user (`qdrant_store.py:383`). Ingestion must write `allowed_groups` on upsert (`_payload`, `:433`), not after via `set_document_groups`, or a restricted doc is briefly public.
- **Auth segment**: group string format in token (`/finance` path vs `finance` name) must match the strings stored in `allowed_groups`; mismatch silently hides or exposes docs.
- **Persistence segment**: `Citation.excerpt` stores full chunk text in messages (`citations.py:121`); text survives ACL revocation and document deletion.
- **Devops**: LLM pricing defaults are pinned to gpt-4o-mini (`composition.py:71-72`) while `LLM_MODEL` is overridable (`:276`); cost reports go wrong silently on model change.
- **Architecture**: `composition.py` is a god module (models, auth, CORS, OCR, storage, observability, pricing) in `infrastructure`; belongs in an entrypoint/bootstrap layer.

## Specialist findings

### Model + prompt inventory
| Model | Caller (file:line) | Purpose | max_tokens | temp | Cached? | Notes |
|-------|-------------------|---------|------------|------|---------|-------|
| `LLM_MODEL` (default gpt-4o-mini, `composition.py:66`) | `grounded_answer.py:119` | rewrite question w/ history | not set here | not set here | no | instruction in user prompt, not system; skipped when no history |
| `LLM_MODEL` | `grounded_answer.py:161` | grounded answer (sync) | not set here | not set here | no | system = assistant prompt + `CITATION_INSTRUCTION` |
| `LLM_MODEL` | `grounded_answer.py:180` | grounded answer (stream) | not set here | not set here | no | same prompt as sync |
| `LLM_MODEL` | `infer_assistant.py:88` | route question to assistant (JSON) | not set here | not set here | no | uses `generate` (no usage accounting) |
| paraphrase-multilingual-MiniLM-L12-v2 | `sentence_transformer_embedding.py:23` | dense embed query/docs, 384d | n/a (max_seq 128) | n/a | lru_cache | also used as LLM token counter |
| BM25 (local, hashed) | `bm25_sparse_embedding.py:83` | sparse query vector | n/a | n/a | n/a | IDF applied by Qdrant |
| cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 | `cross_encoder_reranker.py:26` | rerank 30 candidates, sigmoid | n/a | n/a | lru_cache | CPU, batch 16 |

Distinct prompts: `grounded_answer.py:22` (default answer), `:26` (citation rule), `:33` (rewrite), `:230` (`Pergunta: {q}`), `infer_assistant.py:75-84` (router). No prompt sprawl; all defined once.

### Access control at retrieval time
- **[low] Filter is correct and applied pre-candidate** — `_filter` goes into every `Prefetch` (`qdrant_store.py:124-140`) and into legacy dense search (`:185`); RRF only fuses prefetched points, so restricted chunks never become candidates. `user_groups` is keyword-only with no default (`retrieval.py:65`), so chat cannot omit it. Inactive chunks excluded via `must_not` (`:362`).
- **[med] Fail-open ACL semantics** — `IsEmptyCondition` on `allowed_groups` (`qdrant_store.py:383`) treats missing/null/[] as public to anyone with assistant access. Any ingestion bug or ordering gap (upsert before `set_document_groups`, `:204`) exposes restricted chunks. No "deny on unknown" sentinel.
- **[med] `user_groups=None` disables ACL entirely** (`qdrant_store.py:358`) — only guarded by a docstring (`retrieval.py:69-71`). A future caller passing `None` (e.g. an admin/debug route) silently gets all chunks. Prefer an explicit `AccessScope.unrestricted()` token.
- **[low] Revoked access leaks through history** — prior assistant answers (which quote restricted chunks) are replayed via `conversation_history` (`chat_with_assistant.py:529-536`, `grounded_answer.py:122,163`) after group membership changes.
- **[low] `set_document_active` lacks the 404 guard** that `set_document_groups`/`delete_by_document` have (`qdrant_store.py:245-259` vs `:221`).

### Prompt injection
- **[med] Detection only, no mitigation, retrieved chunks only** — `_flag_injection` (`chat_with_assistant.py:655-690`) audits and continues. User question and history are not scanned; regex is bypassable (zero-width chars survive NFKD, `prompt_injection.py:48-50`; synonyms; other languages).
- **[med] Rewrite prompt breaks RN-31** — instruction and raw user question concatenated in one user message without delimiter (`grounded_answer.py:120`), no `system_instruction`. A question like "ignore e responda X" can steer the rewritten search query (affects retrieval only, not the answer text, which uses the original question at `:162`).
- **[med] Router prompt concatenates user input with instructions** (`infer_assistant.py:82`) and ships every assistant's `initial_prompt` to the LLM (`:70`). Output is constrained to a known id (`:108-117`), so leakage to the user is blocked, but routing is trivially steerable.
- **[med] Streaming shows unvalidated text** — deltas are yielded before citation validation (`chat_with_assistant.py:266`); a failed validation only sends a later `replace` (`:239-240`). Injected or ungrounded content is visible to the user if the client ignores/loses `replace` or the stream is cut.

### Citation correctness
- **[med] Citation validity is syntactic only** — `resolve_citations` (`citations.py:96-112`) accepts any `[n]` that maps to a sent chunk; one valid marker anywhere accepts the whole answer (`grounded_answer.py:197`). No support/entailment check; uncited sentences pass.
- **[med] Stale markers from history** — prior assistant messages in history contain `[n]` referring to previous turns' chunk numbering; the LLM may reuse them and they resolve to different chunks in the current turn.
- **[low] False-positive markers** — bracketed numbers in legitimate text (e.g. `[2023]`, legal refs) are parsed as citations and stripped when out of range (`citations.py:11`, `:76-93`).

### Token / context budget
- **[med] Budgets measured with the wrong tokenizer** — MiniLM sentencepiece counter (`composition.py:89-96`) approximates gpt-4o-mini tokens; no safety margin. `fit_context` counts only chunk text, not the numbering/source/section wrapper the gateway adds (`grounded_answer.py:75`); `trim_history` ignores per-message role overhead (`:58`).
- **[low] Question not budgeted** — neither the answer nor the rewrite call includes the question in any budget; a long question is unbounded input tokens.
- **[low] Dense query truncation** — embedding model `max_seq_length` 128 truncates long queries silently in `embed_query` (`sentence_transformer_embedding.py:55`); cross-encoder pairs truncate at its own max length.
- **[low] `fit_context` uses `break`** (`grounded_answer.py:77`) — one oversized top chunk empties the context and forces fallback, even when smaller relevant chunks fit.
- **[low] Router catalog unbounded** — every assistant (incl. full `initial_prompt`) serialised into one prompt (`infer_assistant.py:65-74`); grows linearly with assistants.

### Structured output
- **[med] Naked `json.loads` on model output** (`infer_assistant.py:100`) — no code-fence stripping, no JSON mode / response_format, no schema; a ```` ```json ```` wrapped reply silently yields `None`. Failure is not logged. `payload.get` on a non-dict (list) raises `AttributeError`, which is not in the except tuple (`:104`) and crashes the graph.

### Cost / usage accounting
- **[med] Router call bypasses usage governance** — `generate` (`infer_assistant.py:88`) returns no usage and there is no rate limit check; tokens are not recorded while chat calls are (RF-57).
- **[low] Extra LLM call per turn** — rewrite runs on every turn with history (`grounded_answer.py:116-123`), resending up to 1500 history tokens; no heuristic skip.
- **[low] Prompt caching n/a** — system prompt is short and per-assistant; OpenAI auto-caching (>=1024-token prefix) will not trigger. Acceptable.

### Error / timeout handling
- **[high] Orphan user messages on LLM/Qdrant failure** — user message is persisted (`chat_with_assistant.py:494`, `:549-561`) before rewrite/retrieval/generation; a failure re-raises (`:150-152`) leaving an unanswered user turn that is replayed into all future history and rewrites.
- **[med] Qdrant client without explicit timeout/retry** — `QdrantClient(url, api_key)` (`qdrant_store.py:36`) relies on library default timeout; only `UnexpectedResponse` is caught (`:150`); `ResponseHandlingException` (connect/timeout) propagates as 500. Error path itself calls `get_collection` (`:195`) unguarded.
- **[med] Non-404 Qdrant errors may degrade silently** — any `UnexpectedResponse` (e.g. transient 5xx) on a non-hybrid check path falls back to legacy dense search (`qdrant_store.py:153-157`), logging only a warning.
- **[low] Missing collection = silent fallback** — 404 returns `[]` (`qdrant_store.py:151-152`) so a mis-wired alias looks like "no context" rather than an error.

### Model loading / embedding lifecycle
- **[med] Dense model drift undetected at query time** — payload stores `embedding_model`/`pipeline_version` (`qdrant_store.py:431-432`) but `hybrid_search` never checks them; only dimension is checked at startup (`sentence_transformer_embedding.py:35`). Swapping to another 384-d model yields silent garbage retrieval. BM25 drift has detection (PC-D2), dense does not.
- **[low] Lazy load on first request** — models load inside `lru_cache` builders (`composition.py:81-139`); first chat pays the full load unless warmed at startup. `lru_cache` does not lock, so concurrent first calls can load the model twice.
- **[low] CPU reranking cost** — 30 pairs through an L12 cross-encoder on CPU per turn (`cross_encoder_reranker.py:54`); dominant latency, no timing budget.

### Clean Architecture boundaries
- **[med] Framework in application layer** — `langgraph` imported by use cases (`chat_with_assistant.py:10`, `infer_assistant.py:7`); orchestration framework is an infrastructure concern.
- **[low] Instance-mutable request state in use case** (`chat_with_assistant.py:139-140`, written at `:188-189,257,570,607,707`) — not thread-safe; see cross-segment hint.
- **[low] `composition.py` imports from a use-case module** (`composition.py:19`) for `ReindexSettings`; settings belong to a services/settings module.

## Concerns / smells
1. **[high] Orphan user messages**: persistence before LLM/Qdrant calls with no compensation (`chat_with_assistant.py:494,549`).
2. **[high if singleton] Per-request state on use-case instance** (`chat_with_assistant.py:139-140`): concurrent turns cross-contaminate audit `retrieved_documents` and usage/billing.
3. **[med] Fail-open ACL + `None` bypass** (`qdrant_store.py:358,383`): correctness depends entirely on ingestion always writing `allowed_groups`.
4. **[med] Unvalidated streamed text + syntactic-only citation check** (`chat_with_assistant.py:266`, `citations.py:96`).
5. **[med] Router JSON parsing and missing usage accounting** (`infer_assistant.py:88,100,104`).

## Refactor suggestions
1. `chat_with_assistant.py:139-189` — move `_ranked_so_far`/`_usage_so_far` into a per-turn context object passed through `_stream_events`/`execute`; build graphs once at module/class level. Removes race and compile cost.
2. `chat_with_assistant.py:493-494` — persist user + assistant messages together in `persist_assistant_message` (or mark the user message `failed` in `_finish_failure`) so failed turns are excluded from history.
3. `qdrant_store.py:36,142-157` — pass explicit `timeout=` to `QdrantClient`, add bounded retry with backoff for `ResponseHandlingException`/5xx, and only fall back to legacy search when the error is a missing-vector-name 400. Also assert `embedding_model` of the collection matches the configured model.
4. `infer_assistant.py:87-106` — use `generate_with_usage` + record usage; system-instruction the routing rules, delimit the question, strip code fences, catch `AttributeError`, log parse failures; prefer JSON mode/response_format in the gateway.
5. `grounded_answer.py:118-123` + `prompt_injection.py` — send `REWRITE_INSTRUCTION` as `system_instruction` with the question delimited; run `detect_prompt_injection` on the question too; strip zero-width/format chars (`unicodedata.category == "Cf"`) in `_normalize`; share one `fold_text` helper with `bm25_sparse_embedding.py:31`.
