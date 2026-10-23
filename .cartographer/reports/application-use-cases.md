# Segment: application-use-cases

**Reviewed by:** generalist-reviewer

## Files reviewed
- `backend/src/application/services/access_control.py`
- `backend/src/application/services/document_indexing.py`
- `backend/src/application/services/grounded_answer.py`
- `backend/src/application/services/index_state.py`
- `backend/src/application/services/ingestion.py`
- `backend/src/application/services/retrieval.py`
- `backend/src/application/services/usage.py`
- `backend/src/application/use_cases/audit_and_session.py`
- `backend/src/application/use_cases/chat_with_assistant.py`
- `backend/src/application/use_cases/check_consistency.py`
- `backend/src/application/use_cases/compare_evaluation_reports.py`
- `backend/src/application/use_cases/create_assistant.py`
- `backend/src/application/use_cases/evaluate_assistant.py`
- `backend/src/application/use_cases/infer_assistant.py`
- `backend/src/application/use_cases/ingest_document.py`
- `backend/src/application/use_cases/list_assistants.py`
- `backend/src/application/use_cases/list_conversations.py`
- `backend/src/application/use_cases/list_groups.py`
- `backend/src/application/use_cases/manage_api_key.py`
- `backend/src/application/use_cases/manage_archived_conversations.py`
- `backend/src/application/use_cases/manage_assistant_access.py`
- `backend/src/application/use_cases/manage_conversation.py`
- `backend/src/application/use_cases/manage_documents.py`
- `backend/src/application/use_cases/manage_feedback.py`
- `backend/src/application/use_cases/manage_usage.py`
- `backend/src/application/use_cases/process_ingestion.py`
- `backend/src/application/use_cases/register_conversation.py`
- `backend/src/application/use_cases/reindex_assistant.py`

## Integrations
- none (grep confirms zero imports of `src.infrastructure`, `src.api`, fastapi, sqlalchemy in `src/application`; only third-party framework import is `langgraph`)

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `services/access_control.py` | `AuditTrail` | class | Appends audit events; no update/delete (RN-25) |
| `services/access_control.py` | `AccessControl` | class | Single gateway to `AccessPolicy` + audit on denial |
| `services/document_indexing.py` | `DocumentIndexer` | class | Extract, chunk, embed (dense+sparse) into `VectorChunk`s |
| `services/document_indexing.py` | `hash_content` | function | sha256 of raw bytes |
| `services/grounded_answer.py` | `GroundedAnswerGenerator` | class | Query rewrite, answer generation, citation validation |
| `services/grounded_answer.py` | `trim_history` / `fit_context` | function | Token-budget trimming of history / context |
| `services/index_state.py` | `IndexState`, `read_index_state`, `is_index_outdated` | class/function | Alias/collection versioning state (RN-16) |
| `services/index_state.py` | `check_sparse_parameters`, `record_sparse_parameters` | function | BM25 parameter drift tracking (PC-D2) |
| `services/ingestion.py` | `IngestionSettings`, `WORKER_USER`, `*_REASON` | class/const | Retry policy and failure reasons (D7) |
| `services/retrieval.py` | `ContextRetriever`, `RetrievalSettings` | class | Hybrid search, rerank, min-score filter |
| `services/usage.py` | `UsageGovernance`, `UsageSettings` | class | Limit check and consumption recording (RF-57/59) |
| `use_cases/audit_and_session.py` | `DescribeCurrentUser`, `ListAuditEvents`, `PurgeAuditEvents` UCs | class | Session start, audit query, retention purge |
| `use_cases/chat_with_assistant.py` | `ChatWithAssistantUseCase` | class | LangGraph chat turn, sync and streaming (794 lines) |
| `use_cases/check_consistency.py` | `CheckIndexConsistencyUseCase` | class | Postgres vs Qdrant count comparison (CLI) |
| `use_cases/compare_evaluation_reports.py` | `CompareEvaluationReportsUseCase` | class | Metric regression detection (RN-14) |
| `use_cases/create_assistant.py` | `CreateAssistantUseCase` | class | Admin creates assistant |
| `use_cases/evaluate_assistant.py` | `EvaluateAssistantUseCase` | class | Recall/MRR/faithfulness evaluation |
| `use_cases/infer_assistant.py` | `InferAssistantUseCase` | class | LLM picks assistant for a question (4-node graph) |
| `use_cases/ingest_document.py` | `Ingest/Replace/ReprocessDocumentUseCase`, `_DocumentIntake` | class | Validate, store, enqueue (427 lines) |
| `use_cases/list_*.py` | `ListAssistants/Conversations/AvailableGroups` UCs | class | Read-only listings with access checks |
| `use_cases/manage_api_key.py` | `Save/GetStatus/GetValue` API-key UCs, `SecretCipher` | class/Protocol | Global LLM key handling |
| `use_cases/manage_archived_conversations.py` | `List/Get/DeleteArchivedConversation` UCs | class | Admin-only legacy conversations |
| `use_cases/manage_assistant_access.py` | `DeleteAssistant`, `SetAssistantGroups`, `ListDocuments`, `SetDocumentGroups` UCs | class | Assistant deletion and group bindings |
| `use_cases/manage_conversation.py` | `Get/Delete/AddMessage` UCs, `load_owned_conversation` | class | Owner-scoped conversation operations |
| `use_cases/manage_documents.py` | `GetDocumentUseCase`, `DeleteDocumentUseCase` | class | Document read and cascading delete |
| `use_cases/manage_feedback.py` | `Submit/List/Review/ExportValidated` feedback UCs | class | Answer feedback and curation |
| `use_cases/manage_usage.py` | `GetUsageReport`, `GetUsageLimits`, `UpdateUsageLimits` UCs | class | Admin usage reporting and limits |
| `use_cases/process_ingestion.py` | `ProcessNextIngestionJobUseCase`, `RequeueExpired...`, `_IngestionFailures` | class | Worker indexing, retry/fail policy |
| `use_cases/register_conversation.py` | `RegisterConversationUseCase` | class | Create owned conversation |
| `use_cases/reindex_assistant.py` | `StartReindex`, `RunReindex`, `ProcessNextReindexJob`, `GetIndexStatus`, `ReportSparseParameterChanges` UCs, `ReindexSettings` | class | Reindex lifecycle (492 lines, 5 UCs) |

## Conventions observed
- **Naming**: snake_case modules/functions, PascalCase classes; `<Verb><Noun>UseCase` with `execute()`; `<Verb><Noun>Input` frozen slotted dataclasses. Modules named `manage_*` are grab-bags.
- **Error handling**: mixed. Domain exceptions (`AccessDeniedError`, `DomainValidationError`, `ReindexInProgressError`) plus application-defined exceptions subclassing `ValueError` or `LookupError`, plus bare `ValueError` for input validation.
- **Logging**: stdlib `logging` with dotted event names + `extra={}` (`chat.rewrite.failed`); audit trail via `AccessControl.audit`; metrics via `MetricsRecorder`.
- **Async style**: fully synchronous.
- **Type hints**: fully typed except `_build_graph` (`chat_with_assistant.py:434`, `infer_assistant.py:51`), `_add_preparation(graph)`, `_stream_answer` return.
- **Language**: docstrings Portuguese ASCII (no accents); exception messages English; `services/ingestion.py:19-37` Portuguese WITH accents.
- **Clean Architecture**: compliant on direction (domain ports only; DTOs from `application.dto`). Two deviations: langgraph in application, ports/exceptions declared in use-case modules.

## Internal duplication
- `_utc_now()` defined 6 times: `access_control.py:21`, `usage.py:28`, `manage_usage.py:26`, `manage_feedback.py:39`, `process_ingestion.py:53`, `reindex_assistant.py:46`; plus inline lambda `audit_and_session.py:136`.
- "Load document, 404 if missing or REPLACED": `manage_documents.py:46,81`, `ingest_document.py:312,393`. Extract `load_active_document()`.
- "Reject if reindex running": `manage_documents.py:89`, `manage_assistant_access.py:189`, `process_ingestion.py:294`, `reindex_assistant.py:87`. Extract `ensure_no_reindex(assistant_id)`.
- `_DocumentIntake` built with the same 7 kwargs twice: `ingest_document.py:221` and `:298`.
- `require_assistant_access` / `require_document_management` (`access_control.py:172-193`) differ only by the policy call.
- Fallback decision (validate then fallback) re-implemented in `evaluate_assistant.py:135-150` vs chat graph (`chat_with_assistant.py:714-750`); acknowledged in comment but can drift.
- Retry defaults 3 / 600 duplicated: `IngestionSettings` (`ingestion.py:48,50`) vs `ReindexSettings` (`reindex_assistant.py:290-291`).

## Cross-segment hints
- `src/api/routes/assistants.py:119` builds `InferAssistantUseCase` per request (compiles a LangGraph each call) and does the RF-42 filtering in the route; belongs in the use case (api segment).
- `src/api/routes/conversations.py:171,494` calls `GetConversationUseCase.removed_sources` directly (a non-`execute` method) and builds citation state in the route.
- `SecretCipher` Protocol (`manage_api_key.py:17`) is a port; belongs in domain, with `FernetSecretCipher` (`infrastructure/secrets`) implementing it.
- `DocumentIndexer.sparse_parameters` uses `getattr(..., "parameters", None)` on the gateway (`document_indexing.py:53`); domain `SparseEmbeddingGateway` port should expose it (domain segment).
- Exceptions `ConversationNotFoundError`, `AssistantNotFoundError`, `DocumentNotFoundError`, `MessageNotFoundError`, `FeedbackNotFoundError`, `DocumentTooLargeError` are mapped to HTTP by the API layer; relocate to a shared errors module (domain/application) and standardize bases.
- `ReindexSettings`/`IngestionSettings` are imported by `infrastructure/composition.py` and `cli/worker.py` straight from use-case modules; configuration segment.
- Worker/CLI identities (`WORKER_USER` in services, `MAINTENANCE_USER` in use_cases) are system identities that belong in one place (domain).

## Specialist findings

### Clean Architecture compliance
- Direction is clean: no `src.infrastructure` / `src.api` imports in the segment (grep verified). severity: none.
- **Framework in application layer** (med): `langgraph` imported at `chat_with_assistant.py:10` and `infer_assistant.py:7`. The orchestration is a control-flow detail wired to a third-party framework; `type: ignore[import-untyped]` markers show it. For `infer_assistant.py` the graph is a strictly linear 4-step chain (`:53-61`), pure ceremony for 4 function calls. Why: couples use cases and their tests to langgraph, hurts replaceability.
- **Ports declared in the application layer** (low): `SecretCipher` Protocol `manage_api_key.py:17`.
- **Use case depends on use case modules for errors** (low): `manage_conversation.py:28` and `manage_archived_conversations.py:24` import from `chat_with_assistant`; `manage_documents.py:24` and `ingest_document.py:43` import from `manage_assistant_access`. Why: hidden coupling and import-cycle risk; a shared `errors.py` fixes it.
- **`AccessControl.permissions` leaks the raw repository** (low): `access_control.py:75`, used at `manage_assistant_access.py:98,138`, `ingest_document.py:172,328,426`, `process_ingestion.py:254`. Use cases bypass the facade whose purpose is to be the single entry point.
- **Infrastructure-aware duck typing** (low): `document_indexing.py:53` (see hints).
- **Vendor default in application** (low): `UsageSettings.model = "gpt-4o-mini"` (`usage.py:38`); `UsageGovernance.record` stamps this configured value (`usage.py:101`) rather than the model that actually answered, so cost attribution is wrong if the gateway model differs.

### Transaction and ownership boundaries
- **No unit of work; multi-step writes use hand-rolled compensation** (med). Examples: `ingest_document.py:149-180` (file save, doc save, groups, enqueue; the compensating `documents.delete` / `_discard_file` can mask the original exception), `ingest_document.py:402-414` (reprocess rollback `save(document)` can itself fail), `manage_assistant_access.py:197-206` (group rollback). Why: partial states (pending document with no job, DB groups differing from Qdrant payload) when compensation fails.
- **Reindex post-swap persistence is non-atomic** (high): `reindex_assistant.py:178-185`. After `_swap_alias` deletes the old collection (`:275`), documents are saved one by one. A failure mid-loop is caught by `except Exception` with `swapped=True`: the job is marked failed, the alias already points to the new collection, but remaining documents keep the old `embedding_model` / `pipeline_version`. `is_index_outdated` (`index_state.py:58`) then reports the index outdated and `_require_current_index` (`ingest_document.py:121`) blocks all uploads until another reindex. Fix: persist document metadata in one repository transaction (bulk save) and/or make the swap step the last, with retry of the bulk save.
- **DeleteAssistant order and leaks** (med): `manage_assistant_access.py:54-60`. DB row deleted first, vector collection after: if Qdrant fails, the assistant is gone, the collection is orphaned and no audit event is written (audit at `:61` is skipped). It also never deletes original files from `DocumentFileStorage` (not injected), leaving orphans, and does not check for a running reindex or ingestion job (compare the guard in `manage_documents.py:89`). Contrast with the careful ordering in `DeleteDocumentUseCase` (`manage_documents.py:93-102`).
- **Audit after commit** (med): every mutating UC audits after the write (`create_assistant.py:51-61`, `manage_usage.py:142-153`, ...). If the audit insert fails, the client gets an error although the change is committed and unaudited. No outbox or same-transaction guarantee; RN-25 audit completeness is best-effort.
- **Existence disclosure via 403 vs 404** (low-med): document operations load the document first (404) and only then check permission: `manage_documents.py:46-50,81-85`, `ingest_document.py:311-317,392-397`, `manage_assistant_access.py:180-185`. A non-manager can probe document ids. Conversations deliberately avoid this (`manage_conversation.py:1-5`); inconsistent.
- **`AddMessageUseCase` accepts client-chosen role** (med): `manage_conversation.py:123-146` does `MessageRole(data.role)` with no restriction. A user can forge `assistant` messages in their own conversation; these flow into LLM history (`chat_with_assistant.py:527`), are eligible for `SubmitFeedback` (`manage_feedback.py:72` only requires role ASSISTANT) and bypass usage limit, assistant access check (`require_assistant_access` is used in chat/register but not here) and audit. Restrict to `USER`/system or drop the UC if unused.
- **Usage limit check and record are separate** (low-med): `usage.py:68` checks at turn start, `record` at the end; concurrent turns by one user all pass the per-minute check before any is recorded.
- **Reindex lifecycle not audited** (low-med): only start is audited (`reindex_assistant.py:109`); completion, failure and abandonment (`:186-194`, `:346-360`) are logs only, unlike ingestion (`process_ingestion.py:118,361`).
- **StartReindex TOCTOU** (low, related to the already reported reindex race): `get_running` then `save` (`reindex_assistant.py:87-108`) and PROCESSING scan (`:95`) are not atomic with the worker.

### Error handling consistency
- **Not-found types are inconsistent** (med): `ConversationNotFoundError(ValueError)` (`chat_with_assistant.py:57`), `MessageNotFoundError(ValueError)`, `FeedbackNotFoundError(ValueError)` (`manage_feedback.py:31,35`) vs `AssistantNotFoundError(LookupError)`, `DocumentNotFoundError(LookupError)` (`manage_assistant_access.py:25,29`). Five exceptions, two bases; NotFound-as-ValueError collides with real validation `ValueError`s, so the API must order its handlers carefully.
- **Validation errors use bare `ValueError` vs `DomainValidationError`** (low-med): `manage_api_key.py:54`, `evaluate_assistant.py:61,63`, `compare_evaluation_reports.py:27`, `infer_assistant.py:39`, `chat_with_assistant.py:168`, `ingest_document.py:94,106`, `manage_feedback.py:194` vs `audit_and_session.py:144`.
- **Worker misclassifies provider faults as permanent** (med): `process_ingestion.py:158` treats any `ValueError` as `UNREADABLE_DOCUMENT_REASON` (definitive, no retry). `document_indexing.py:87-90` raises `ValueError("embedding provider returned an unexpected vector count")`, a transient provider fault, so the document is failed permanently with a misleading "unreadable" message. Use a dedicated exception.
- **Rewrite fallback catches too little** (low-med): `grounded_answer.py:124` catches only `(ValueError, RuntimeError)` although the docstring says any LLM failure falls back to the original question; timeouts/HTTP errors from the gateway propagate and fail the whole turn.
- **Denial audit labels are imprecise** (low): `require_admin` always logs `AuditResource.SETTINGS` (`access_control.py:125`) even for assistants, conversations, usage. Read UCs pass change-actions as "attempted": `manage_api_key.py:80` (`LLM_API_KEY_CHANGED` for a status read), `manage_usage.py:111` (`USAGE_LIMITS_CHANGED` for a read).
- **Raw string action names** (low): `"conversation.list"` (`list_conversations.py:30`), `"conversation.create"` (`register_conversation.py:38`), `"document.list"` (`manage_assistant_access.py:136`), `"document.read"` (`manage_documents.py:50`), `"index.status"` (`reindex_assistant.py:392`), `"groups.listed"` (`access_control.py:166`) while `AuditAction` exists; hence `AuditAction | str` unions (`access_control.py:176,188,198`). Add enum members.
- **Pagination bounds inconsistent** (low): audit caps `limit` at 200 but allows `limit<=0` and negative `offset` (`audit_and_session.py:85-86`); usage clamps both (`manage_usage.py:67`); `ListFeedback` passes `limit`/`offset` unvalidated (`manage_feedback.py:160-161`).

### Usage governance bypass
- `InferAssistantUseCase` (`infer_assistant.py:87-93`) calls `llm_gateway.generate` directly: no `UsageGovernance.check` and no `record`, so `/assistants/infer` consumes tokens outside RF-57/RF-59 limits and reports. Inject `UsageGovernance` or document the exemption. The assistant list is passed as untyped `list[dict[str, str | None]]` (`:15`) rather than DTOs, and the RF-42 filter is done by the route, not enforced by the use case. Not-parseable LLM output and gateway errors are not distinguished.

### Cohesion assessment
- Recommendation: keep as one segment but split the oversized modules; two modules misnamed.
- Reasoning: all files honour the layer boundary and share conventions. Cohesion problems are intra-segment: `chat_with_assistant.py` (794 lines, one class of ~35 methods, 3 compiled graphs, audit/usage/metrics/injection concerns), `reindex_assistant.py` (492 lines, 5 use cases + settings mid-file at `:283`), `ingest_document.py` (427), `process_ingestion.py` (419). `manage_assistant_access.py` mixes assistant deletion, group binding, document listing and document group binding plus two shared exceptions; `ListDocumentsUseCase` belongs in `manage_documents.py`.
- If split (proposed):
  - `chat/`: `chat_turn.py` (use case + execute/stream), `chat_graph.py` (nodes/wiring), `chat_audit.py` (`_audit_*`, `_retrieved`, usage recording, injection flagging).
  - `reindex/`: `start_reindex.py`, `run_reindex.py`, `process_reindex_job.py` (+`ReindexSettings`), `index_status.py` (+ sparse report).
  - `assistants/`: `create_assistant.py`, `delete_assistant.py`, `set_assistant_groups.py`, `list_assistants.py`, `infer_assistant.py`.
  - `documents/`: `ingest_document.py`, `replace_document.py`, `reprocess_document.py`, `list_documents.py`, `get_document.py`, `delete_document.py`, `set_document_groups.py`.
  - `errors.py`: all NotFound / TooLarge exceptions.
  - Move `WORKER_USER`, `MAINTENANCE_USER` to one identity module.

### Deletability / dead code candidates
- `GroundedAnswerGenerator.rewrite_question` (`grounded_answer.py:99-104`): no caller in `src` (chat uses `rewrite`); only a thin wrapper. Candidate for removal.
- `GroundedAnswerGenerator.generate` (`:135-148`): used only by `answer()`; collapse into `generate_completion`.
- `hash_content` computed twice per upload (`ingest_document.py:111`, `document_indexing.py:91`); imported by deep path bypassing the package (`ingest_document.py:21`).
- `ReindexSettings` docstring (`reindex_assistant.py:285-288`) says it reuses ingestion env values but duplicates defaults rather than reusing them.
- `SPARSE_PARAMETERS_CHANGED_METRIC` (`reindex_assistant.py:53`) is emitted only by the startup report, not by `GetIndexStatusUseCase` (`:402-403` logs only). Verify intent.

### Size and complexity
- Classes: `ChatWithAssistantUseCase` ~690 lines (`chat_with_assistant.py:104-766`).
- Functions >50 lines: `CheckIndexConsistencyUseCase._check` 54 (`check_consistency.py:105-158`), `GetIndexStatusUseCase.execute` 50 (`reindex_assistant.py:389-438`), `_stream_events` borderline.
- Magic values: supported formats literal `ingest_document.py:106-109` duplicates extractor knowledge (and `supports` is called twice with/without content_type at `:96-105`, an undocumented coupling to worker behaviour); `MAX_ITEMS = 1000` (`manage_feedback.py:232`); `tolerance=0.02` (`compare_evaluation_reports.py:16`); `PIPELINE_VERSION = "3"` is a string compared for equality.
- Performance: `GetConversationUseCase.removed_sources` does one `get_by_id` per cited document (`manage_conversation.py:79`, N+1); `SubmitFeedback` loads the full message history to find one question (`manage_feedback.py:80`); `build_chunks` embeds all chunks in one call without batching (`document_indexing.py:85-86`).
- `ContextRetriever.search(user_groups=None)` silently disables RF-43 filtering (`retrieval.py:65-71`); a keyword-only Optional is an easy footgun, prefer an explicit `search_unrestricted()` for the evaluation path (`evaluate_assistant.py:124-128`).

### Missing tests / type gaps
- Tests not reviewed per instructions. Type gaps: untyped `graph` params and return types listed under Conventions.
- No TODO/FIXME found in the segment.

## Concerns / smells
1. (high) Reindex post-swap document persistence is non-atomic and can leave the index permanently "outdated" with uploads blocked: `reindex_assistant.py:178-185`.
2. (med) `AddMessageUseCase` lets users forge `assistant` role messages, with no access/usage/audit control: `manage_conversation.py:123-146`.
3. (med) `DeleteAssistantUseCase` orders DB-then-Qdrant without recovery, skips audit on failure and leaks original files: `manage_assistant_access.py:51-67`.
4. (med) Worker treats any `ValueError` (including provider vector-count mismatch) as permanent "unreadable document": `process_ingestion.py:158` + `document_indexing.py:87`.
5. (med) Inconsistent exception taxonomy (NotFound as ValueError vs LookupError), langgraph in application layer, and `infer_assistant` bypassing usage governance.

## Refactor suggestions
1. `reindex_assistant.py:178-185`: add `DocumentRepository.save_many` (single transaction) and persist document metadata atomically with job success; on failure after swap, record a distinct "swapped but unsynchronized" state. Why: avoids stuck-outdated index.
2. New `application/errors.py`: move `ConversationNotFoundError`, `AssistantNotFoundError`, `DocumentNotFoundError`, `MessageNotFoundError`, `FeedbackNotFoundError`, `DocumentTooLargeError` under one `NotFoundError(LookupError)` base (and a `DocumentIndexingError` for provider faults, so `process_ingestion.py:158` stops catching bare `ValueError`). Why: removes cross-use-case imports and ambiguous mapping.
3. Split `chat_with_assistant.py` per the cohesion proposal and hide langgraph behind a small `TurnPipeline` seam (or drop it for `infer_assistant.py`, replacing the 4-node graph with 4 method calls). Why: 794-line class, framework in application layer.
4. Extract shared guards into `application/services/guards.py`: `load_active_document`, `ensure_no_reindex`, `utc_now`; add missing `AuditAction` members and tighten `require_*` signatures to `AuditAction` only. Why: removes 4 duplicated patterns and `AuditAction | str`.
5. `manage_conversation.py:123` and `infer_assistant.py`: restrict `AddMessageUseCase` roles (or delete it if the API does not need it) and inject `UsageGovernance` into `InferAssistantUseCase`; move RF-42 filtering for infer into the use case. Why: closes the forged-history and usage-limit bypass paths.
