# Cross-segment synthesis

- Segments reviewed: **8**
- Project naming convention: **snake**
- Duplicate name pairs: **148**
- Naming-convention outlier segments: **7**
- Centralization candidates: **0**
- Style fingerprint outliers: **1**

## Duplicate / near-duplicate functions
- `get_session` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_session` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_tracer` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_tracer` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_metrics` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_metrics` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_token_verifier` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_token_verifier` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_current_user` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_current_user` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `_unauthenticated` in `backend/src/api/dependencies.py` (api-http)  ↔  `_unauthenticated` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_permission_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_permission_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_audit_log_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_audit_log_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_access_control` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_access_control` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_assistant_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_assistant_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_conversation_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_conversation_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_document_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_document_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_secret_settings_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_secret_settings_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_secret_cipher` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_secret_cipher` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_reindex_job_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_reindex_job_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `build_index_parameters_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `build_index_parameters_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `build_index_parameters_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_index_parameters_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_index_parameters_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `build_index_parameters_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_index_parameters_repository` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_index_parameters_repository` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_group_directory` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_group_directory` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_sparse_encoding_parameters` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_sparse_encoding_parameters` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_ingestion_job_queue` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_ingestion_job_queue` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_embedding_gateway` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_embedding_gateway` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_document_indexer` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_document_indexer` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_file_storage` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_file_storage` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_max_file_bytes` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_max_file_bytes` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_vector_store_gateway` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_vector_store_gateway` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_token_counter` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_token_counter` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_context_retriever` in `backend/src/api/dependencies.py` (api-http)  ↔  `get_context_retriever` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- `get_context_retriever` in `backend/src/api/dependencies.py` (api-http)  ↔  `build_context_retriever` in `backend/src/api/dependencies.py` (auth-access-control)  — score 100
- *... 118 more in synthesis.json*

## Naming convention outliers
- **api-http**: dominant `snake` (purity 0.733), distribution {'snake': 77, 'other': 28}
- **application-use-cases**: dominant `other` (purity 0.686), distribution {'other': 24, 'snake': 11}
- **auth-access-control**: dominant `snake` (purity 0.746), distribution {'snake': 44, 'other': 15}
- **database**: dominant `other` (purity 0.878), distribution {'snake': 5, 'other': 36}
- **frontend-core-store**: dominant `camel` (purity 0.87), distribution {'camel': 47, 'other': 7}
- **ingestion-and-worker**: dominant `other` (purity 0.786), distribution {'snake': 12, 'other': 44}
- **rag-retrieval**: dominant `snake` (purity 0.576), distribution {'snake': 34, 'other': 25}

## Style fingerprint outliers
- **frontend-core-store**: 63.8 LOC/symbol (project mean 22.6 ± 18.4)

## Refactor backlog (aggregated from per-segment reports)
_40 items across 8 segments._

- `api-http` via `backend-api-reviewer`: `routes/documents.py:116,230` — check `request.headers["content-length"]` and read `UploadFile` in chunks up to `max_file_bytes + 1`, returning 413 early; move `get_by_id` (`:111`) into the threadpool call or the use case.
- `api-http` via `backend-api-reviewer`: `schemas/conversations.py:31-39` — restrict `AddMessageRequest.role` to `user` (or drop the route if unused by the UI); add `max_length` to `ChatRequest.question`, `InferAssistantRequest.question`, `CreateAssistantRequest.*`, `SaveApiKeyRequest.api_key`.
- `api-http` via `backend-api-reviewer`: `api/errors.py` — register global handlers for `DomainValidationError` (422), `*NotFoundError` (404), `IndexOutdatedError`/`ReindexInProgressError` (409), and an `LLMNotConfiguredError` (503); delete the ~15 per-route try/except blocks and the bare `ValueError`/`RuntimeError` catches; standardise on one envelope `{detail, code}`.
- `api-http` via `backend-api-reviewer`: `routes/{conversations,assistants,documents,index}.py` — move assistant existence checks into the use cases after `AccessControl` (return 404 for both missing and forbidden), removing `_existing_assistant_id` and its copies.
- `api-http` via `backend-api-reviewer`: `routes/admin.py:113-178` — extract `TestGlobalApiKeyUseCase` taking an `LLMGatewayFactory` port; reuse `build_llm_gateway` so `LLM_API_URL` is read in one place; audit after the outcome with success/failure.
- `application-use-cases` via `generalist-reviewer`: `reindex_assistant.py:178-185`: add `DocumentRepository.save_many` (single transaction) and persist document metadata atomically with job success; on failure after swap, record a distinct "swapped but unsynchronized" state. Why: avoids stuck-outdated index.
- `application-use-cases` via `generalist-reviewer`: New `application/errors.py`: move `ConversationNotFoundError`, `AssistantNotFoundError`, `DocumentNotFoundError`, `MessageNotFoundError`, `FeedbackNotFoundError`, `DocumentTooLargeError` under one `NotFoundError(LookupError)` base (and a `DocumentIndexingError` for provider faults, so `process_ingestion.py:158` stops catching bare `ValueError`). Why: removes cross-use-case imports and ambiguous mapping.
- `application-use-cases` via `generalist-reviewer`: Split `chat_with_assistant.py` per the cohesion proposal and hide langgraph behind a small `TurnPipeline` seam (or drop it for `infer_assistant.py`, replacing the 4-node graph with 4 method calls). Why: 794-line class, framework in application layer.
- `application-use-cases` via `generalist-reviewer`: Extract shared guards into `application/services/guards.py`: `load_active_document`, `ensure_no_reindex`, `utc_now`; add missing `AuditAction` members and tighten `require_*` signatures to `AuditAction` only. Why: removes 4 duplicated patterns and `AuditAction | str`.
- `application-use-cases` via `generalist-reviewer`: `manage_conversation.py:123` and `infer_assistant.py`: restrict `AddMessageUseCase` roles (or delete it if the API does not need it) and inject `UsageGovernance` into `InferAssistantUseCase`; move RF-42 filtering for infer into the use case. Why: closes the forged-history and usage-limit bypass paths.
- `auth-access-control` via `auth-security-reviewer`: `infra/keycloak/nexus-realm.json`: split into `nexus-realm.json` (clients, roles, mappers, `full.path: true`, refresh rotation, password policy, `sslRequired: all`) and `nexus-realm.dev-users.json`; fail bootstrap when `${...}` vars are unresolved.
- `auth-access-control` via `auth-security-reviewer`: `backend/src/infrastructure/secrets/cipher.py:13`: accept a proper Fernet key (or scrypt-derived with salt), wrap in `MultiFernet` for rotation; validate in app startup instead of `dependencies.py:177`.
- `auth-access-control` via `auth-security-reviewer`: `backend/src/infrastructure/auth/keycloak_token_verifier.py:90-137`: add `typ`/`azp` checks, leeway, stale-key cap, out-of-lock single-flight refresh, min key size; convert `DomainValidationError` in `_to_user` to `AuthenticationError`.
- `auth-access-control` via `auth-security-reviewer`: `backend/src/application/use_cases/manage_assistant_access.py:178-200`: serialize document-restriction changes with reindex start (advisory lock keyed on assistant id) and authorize via assistant scope before revealing document existence.
- `auth-access-control` via `auth-security-reviewer`: `backend/src/application/services/access_control.py:123-193`: collapse admin-only `require_*` into one `_require(predicate, action, resource, resource_id)` helper and pass the target resource id so `access.denied` events always carry it.
- `database` via `db-schema-reviewer`: `repositories.py:134-165` — Add `list_summaries(assistant_id, owner, limit, cursor)` that selects conversation columns only (plus optional last-message subquery); drop `selectinload(messages)` from listings; keep full load for `get_by_id`.
- `database` via `db-schema-reviewer`: `models.py:43-50,200-204` — Add `passive_deletes=True` to cascade relationships; delete via `delete(Model).where(...)` so PG `ON DELETE CASCADE` does the work.
- `database` via `db-schema-reviewer`: New migration `0008` — Indexes: `conversations(owner_user_id, assistant_id, updated_at DESC)`, `messages(conversation_id, created_at)`, `usage_records(assistant_id)`, `documents(replaces_document_id)`, `audit_events(user_id, occurred_at)`; convert `audit_events.details` to `jsonb` + expression index on `(details->>'assistant_id')`; CHECK constraints for status/role/rating columns. Mirror in `models.py`.
- `database` via `db-schema-reviewer`: `base.py:4` — Set `MetaData(naming_convention=...)` and `env.py:26` `compare_type=True, compare_server_default=True`; align `server_default`s in `models.py` with migrations so autogenerate is clean.
- `database` via `db-schema-reviewer`: `repositories.py` / `operations_repositories.py` — Extract a `_commit()` helper (commit, rollback on exception, map `IntegrityError`) and move toward a Unit of Work where the application layer commits; replace settings/feedback/secret upserts with `postgresql.insert(...).on_conflict_do_update`.
- `devops-infra` via `devops-config-reviewer`: `compose.yaml` (all `env_file` blocks, lines 6-9 etc.): replace the required `.env.example` load with a `.env`-required model or use `${VAR:?}` for secrets (`POSTGRES_PASSWORD`, `QDRANT_API_KEY`, `KEYCLOAK_*`, `NEXUS_SECRETS_KEY`) and scope `environment:` per service. Why: removes silent default secrets and least-privilege leakage.
- `devops-infra` via `devops-config-reviewer`: `compose.yaml` ports (lines 11,69,88,142,167,186,197,213): bind to `127.0.0.1:` for postgres, qdrant, backend, keycloak, prometheus, jaeger, grafana and publish only the frontend. Why: closes direct DB/vector/metrics access and the `/metrics` bypass.
- `devops-infra` via `devops-config-reviewer`: `scripts/backup.sh` + `.github/workflows/ci.yml`: quiesce writers (stop worker, or take Postgres first then Qdrant under a write pause), write `counts.txt` from the dump source, add `set -o pipefail`, and add a CI job that runs backup then restore against ephemeral Postgres/Qdrant service containers plus `shellcheck` over all scripts. Why: proves consistency and restore.
- `devops-infra` via `devops-config-reviewer`: `infra/docker/*.Dockerfile`: add non-root `USER` (or `nginx-unprivileged`), pin base images by digest, switch frontend to `npm ci`, and add `pip-compile`/`uv` lock with hashes plus torch in the lock; align the Qdrant client and server versions. Why: security and reproducibility.
- `devops-infra` via `devops-config-reviewer`: `.github/workflows/ci.yml` and `scripts/quality-gate.sh`: add a `docker compose build` job, `pip-audit`/`npm audit`, Trivy, Dependabot; add `--build` to `compose run` in quality-gate/eval. Why: catches broken images and stale-image gate results.
- `frontend-core-store` via `frontend-ui-reviewer`: `nexus.effects.ts:259` and `nexus-api.service.ts:215-237`: make the stream pipeline emit a failure when it completes without a terminal event, add `cancelChatStream` with `takeUntil`, normalise CRLF and flush the tail on Response. Why: removes the stuck-spinner and lost-last-event bugs.
- `frontend-core-store` via `frontend-ui-reviewer`: `markdown.pipe.ts`: custom marked renderer that strips/rewrites `image` and adds `rel="noopener noreferrer" target="_blank"` to links; fix `decodeHtml` order; throttle input (or memoise by text) during streaming. Why: closes exfiltration channel and cuts re-render cost.
- `frontend-core-store` via `frontend-ui-reviewer`: `auth.service.ts:112-125` + `oidc-client.ts:155`: give `OidcError` an HTTP `status`/`code`, expire only on `invalid_grant`, retry network failures with backoff; strip `code`/`state` from the URL when `completeLogin` throws. Why: avoids spurious logouts and the stuck error loop.
- `frontend-core-store` via `frontend-ui-reviewer`: `nexus.reducer.ts` / `nexus.selectors.ts`: drop flat `documents`, adopt `@ngrx/entity` for assistants/conversations/documents, derive `currentConversationId` from `selectedConversationByAssistant`, use shared `EMPTY` constants and narrow input selectors. Why: removes state duplication and spurious emissions.
- `frontend-core-store` via `frontend-ui-reviewer`: `nexus.effects.ts:525-603`: re-arm polling on failure of background loads (or use `expand`/`repeat`), cap `uploadDocument` concurrency, move `saveBlob` side effect into a `tap` guarded by try/catch. Why: polling and uploads survive transient errors.
- `ingestion-and-worker` via `queue-worker-reviewer`: `process_ingestion.py` + `IngestionJobQueue`: add `renew(job, until)` called from `DocumentIndexer` progress hooks (per page/batch) and make `complete/retry/fail` conditional on `(id, attempts, status='reserved')`; abort work if the update affects 0 rows.
- `ingestion-and-worker` via `queue-worker-reviewer`: `reindex_assistant.py:244`: renew lease inside `_reindex_document` (per OCR page / embed batch) and make `ReindexJobRepository.save` fence on `attempts`; skip `_discard`/`_swap_alias` if ownership is lost.
- `ingestion-and-worker` via `queue-worker-reviewer`: `text_extraction.py:136-190` + `ocr.py`: one shared `_run_tool(cmd, timeout)` helper with timeout, isolated LibreOffice profile, and map `TimeoutExpired` to a dedicated retryable error; run pypdf/docx parsing under a page cap and subprocess with `RLIMIT_AS`.
- `ingestion-and-worker` via `queue-worker-reviewer`: `process_ingestion.py:152`: replace type-based classification with explicit `UnreadableDocumentError` / `TransientServiceError` raised by extractors and gateways; wrap pypdf/docx/zip errors as unreadable.
- `ingestion-and-worker` via `queue-worker-reviewer`: Delete `extract_supported_text`, `_extract_pdf_text`, `_extract_docx_text` (`text_extraction.py:24-113`) and keep only `structured_extraction.py`; move `_extract_doc_text` there. Make `LocalDocumentFileStorage.save` (`local_file_storage.py:35`) atomic and non-overwriting (temp file + `os.replace`, fail if exists).
- `rag-retrieval` via `ai-pipeline-reviewer`: `chat_with_assistant.py:139-189` — move `_ranked_so_far`/`_usage_so_far` into a per-turn context object passed through `_stream_events`/`execute`; build graphs once at module/class level. Removes race and compile cost.
- `rag-retrieval` via `ai-pipeline-reviewer`: `chat_with_assistant.py:493-494` — persist user + assistant messages together in `persist_assistant_message` (or mark the user message `failed` in `_finish_failure`) so failed turns are excluded from history.
- `rag-retrieval` via `ai-pipeline-reviewer`: `qdrant_store.py:36,142-157` — pass explicit `timeout=` to `QdrantClient`, add bounded retry with backoff for `ResponseHandlingException`/5xx, and only fall back to legacy search when the error is a missing-vector-name 400. Also assert `embedding_model` of the collection matches the configured model.
- `rag-retrieval` via `ai-pipeline-reviewer`: `infer_assistant.py:87-106` — use `generate_with_usage` + record usage; system-instruction the routing rules, delimit the question, strip code fences, catch `AttributeError`, log parse failures; prefer JSON mode/response_format in the gateway.
- `rag-retrieval` via `ai-pipeline-reviewer`: `grounded_answer.py:118-123` + `prompt_injection.py` — send `REWRITE_INSTRUCTION` as `system_instruction` with the question delimited; run `detect_prompt_injection` on the question too; strip zero-width/format chars (`unicodedata.category == "Cf"`) in `_normalize`; share one `fold_text` helper with `bm25_sparse_embedding.py:31`.

## Concerns / smells (aggregated)
### api-http
- **high** — Unbounded upload buffering: `await file.read()` before size enforcement (`documents.py:116`, `:230`) enables memory exhaustion.
- **high** — `POST /conversations/{id}/messages` lets clients write `assistant`/`system` turns (`schemas/conversations.py:31-34`), poisoning history fed to the LLM.
- **med** — Assistant existence 404 checked before authorization in 6 routes, giving an ID-enumeration oracle and contradicting RN-24.
- **med** — Error mapping leaks/misclassifies: `ValueError->422` for missing LLM config, `RuntimeError->502` with raw `str(exc)`; four different error envelope shapes.
- **med** — No length caps on chat/infer questions and assistant prompts; several list endpoints unpaged; `/metrics` unauthenticated in-app.

### application-use-cases
- (high) Reindex post-swap document persistence is non-atomic and can leave the index permanently "outdated" with uploads blocked: `reindex_assistant.py:178-185`.
- (med) `AddMessageUseCase` lets users forge `assistant` role messages, with no access/usage/audit control: `manage_conversation.py:123-146`.
- (med) `DeleteAssistantUseCase` orders DB-then-Qdrant without recovery, skips audit on failure and leaks original files: `manage_assistant_access.py:51-67`.
- (med) Worker treats any `ValueError` (including provider vector-count mismatch) as permanent "unreadable document": `process_ingestion.py:158` + `document_indexing.py:87`.
- (med) Inconsistent exception taxonomy (NotFound as ValueError vs LookupError), langgraph in application layer, and `infer_assistant` bypassing usage governance.

### auth-access-control
- Realm file mixes dev seed users with the only realm definition — default admin password ships wherever it is imported.
- Two sources of truth for document restrictions (Postgres + Qdrant payload) with a non-atomic check-then-write against reindex.
- Group matching by leaf name breaks isolation as soon as nested groups exist.
- Audit trail covers app actions well but has no authentication-failure or IdP-side (role/group change) visibility.
- Verifier/directory caching correctness depends on composition-layer singletons not visible in this segment.

### database
- **high** — Conversation listings eager-load every message with no pagination (`repositories.py:134-165`); will degrade linearly with chat history.
- **high** — Missing rollback on failed commits across ~14 write paths; long-lived worker sessions get poisoned (`repositories.py`, `operations_repositories.py`).
- **med** — Repositories own commits: no Unit of Work, so audit + action + group changes are not atomic; audit trail can diverge from reality.
- **med** — Index gaps on hot paths: conversation listing composite, audit `details->>'assistant_id'` on `json`, `usage_records.assistant_id` FK.
- **med** — No CHECK constraints for enum-like status columns; ORM cascades without `passive_deletes` cause N+1 deletes.

### devops-infra
- **High** Default credentials (`nexus`, `admin`, `nexus-local`, `nexus-backend-dev-secret`, `change-me-in-local-env`) ship as the required base env file and nothing fails fast when unchanged, combined with every service published on all host interfaces, including Postgres, Qdrant, Keycloak `start-dev
- **High** Backup is not cross-store consistent (Postgres, Qdrant and files dumped at different moments with writers running) and the restore path is untested in CI (syntax check only).
- **Med** Images run as root, are unpinned by digest, and are about two years old; builds are not reproducible (no lockfile or hashes for Python, `npm install` in the image vs `npm ci` in CI).
- **Med** CI does not build the images, run integration tests, lint beyond F/E9, audit dependencies, or scan secrets; `qdrant-client 1.19.1` vs server `v1.11.3` mismatch goes unchecked.
- **Med** `quality-gate.sh` and `eval.sh` run against the last built image rather than the working tree, so a green gate can describe stale code.

### frontend-core-store
- (high) SSE stream that ends without `done`/`error` leaves `chatStream` and `loading.sendChat` set forever; no cancel action either (`nexus.effects.ts:237-267`, `nexus-api.service.ts:215`).
- (med) Remote images from LLM markdown survive sanitising, enabling zero-click data exfiltration via prompt injection (`markdown.pipe.ts:39`).
- (med) Any refresh failure, including network errors, logs the user out (`auth.service.ts:112-125`).
- (med) Document/index polling stops permanently after one failed poll (`nexus.effects.ts:525-603`).
- (med) Selectors return fresh `[]`/objects and depend on the whole feature state; combined with per-token actions and full markdown re-parse each delta, streaming is O(n²) in re-render work (`nexus.selectors.ts:102-128,159-164`; `nexus.reducer.ts:460`).

### ingestion-and-worker
- No lease renewal / fencing for ingestion jobs and per-document-only renewal for reindex: multi-worker deployments double-process and can delete each other's Qdrant data (`process_ingestion.py:399`, `reindex_assistant.py:208`, `:229-235`).
- Timeout-less subprocesses for `.doc` (`text_extraction.py:139/153/168`) and unbounded in-process parsers: one bad file hangs workers serially (poison pill).
- Exception-type retry classification misroutes corrupt-file and provider errors (`process_ingestion.py:152-160`).
- Non-atomic activation/complete and swap/PG-update sequences leave PG and Qdrant inconsistent after partial failure (`process_ingestion.py:263-275`, `reindex_assistant.py:178-185`).
- No DLQ-style visibility: no metrics or alerts for failed/abandoned jobs or queue depth.

### rag-retrieval
- **[high] Orphan user messages**: persistence before LLM/Qdrant calls with no compensation (`chat_with_assistant.py:494,549`).
- **[high if singleton] Per-request state on use-case instance** (`chat_with_assistant.py:139-140`): concurrent turns cross-contaminate audit `retrieved_documents` and usage/billing.
- **[med] Fail-open ACL + `None` bypass** (`qdrant_store.py:358,383`): correctness depends entirely on ingestion always writing `allowed_groups`.
- **[med] Unvalidated streamed text + syntactic-only citation check** (`chat_with_assistant.py:266`, `citations.py:96`).
- **[med] Router JSON parsing and missing usage accounting** (`infer_assistant.py:88,100,104`).

## Cross-segment hints (raw, for routing)
### From api-http
- **auth/access**: no role is declared at the HTTP layer; all role checks live in `AccessControl` inside use cases. Auth segment must confirm every use case invoked here calls `AccessControl` (esp. `InferAssistantUseCase`, which receives no `access_control`, `assistants.py:119`).
- **config**: `get_secret_cipher` defaults `NEXUS_SECRETS_KEY` to `""` (`dependencies.py:178`) — config segment must confirm Fernet fails closed.
- **config/deploy**: `/metrics` is protected only by Nginx returning 404 (`main.py:105`); verify the backend container port is not published in compose/k8s.
- **config**: `cors_allowed_origins()` contents not visible here; verify no `*` in prod.
- **data**: `get_db_session` commit/rollback semantics determine whether SSE writes persist after dependency teardown (see SSE finding).
- **infrastructure/llm**: `HttpChatCompletionsLLM` exception messages are echoed to clients (`admin.py:170`, `conversations.py:368`); confirm they never include upstream bodies or the API ke

### From application-use-cases
- `src/api/routes/assistants.py:119` builds `InferAssistantUseCase` per request (compiles a LangGraph each call) and does the RF-42 filtering in the route; belongs in the use case (api segment).
- `src/api/routes/conversations.py:171,494` calls `GetConversationUseCase.removed_sources` directly (a non-`execute` method) and builds citation state in the route.
- `SecretCipher` Protocol (`manage_api_key.py:17`) is a port; belongs in domain, with `FernetSecretCipher` (`infrastructure/secrets`) implementing it.
- `DocumentIndexer.sparse_parameters` uses `getattr(..., "parameters", None)` on the gateway (`document_indexing.py:53`); domain `SparseEmbeddingGateway` port should expose it (domain segment).
- Exceptions `ConversationNotFoundError`, `AssistantNotFoundError`, `DocumentNotFoundError`, `MessageNotFoundError`, `FeedbackNotFoundError`, `DocumentTooLargeError` are mapped to HTTP by the API layer; relocate to a shared errors module (domain/application) and standardize bases.
- `ReindexSet

### From auth-access-control
- `get_token_verifier` (`dependencies.py:97`) calls `build_token_verifier()` per request; if `src/infrastructure/composition` does not cache it (lru_cache / module singleton), the JWKS cache is per-request and every request hits Keycloak's JWKS endpoint. Same for `build_group_directory()` (`dependencies.py:204`) — token + group cache would be lost each call. Composition segment must confirm.
- Authentication is per-route (`Depends(get_current_user)`), not global middleware (`middleware.py` has no auth). RF-40 ("every route except /health") relies on every router declaring the dependency — API-routes segment must inventory routes lacking it (also `/metrics`, which `middleware.py:18` treats as a public probe).
- `normalize_request_id` (observability segment) receives client-controlled `X-Request-ID` (`middleware.py:44`) that is echoed in the response and bound into logs/trace IDs — verify length/charset sanitising (log injection).
- Frontend segment: confirm token storage (in-memory vs `

### From database
- **Business rules inside repositories**: conversation auto-naming (truncate to 97 chars + "...") in `repositories.py:182-184`; "no ingestion while assistant reindexing" in `repositories.py:290-304`; "deleted document is not resurrected" (C4) in `repositories.py:352-354`. Belong in application/domain.
- **Transaction ownership**: repositories commit internally, so use cases cannot make multi-repo writes atomic (e.g. assistant save + `set_assistant_groups` + `audit.append`). Route to application segment: introduce Unit of Work.
- **Audit atomicity**: `PostgresAuditLogRepository.append` commits independently (`repositories.py:537`) — audited action and audit row can diverge. Route to auth/audit segment.
- **Metrics in DB layer**: `ingestion_job_gauges` (`operations_repositories.py:379`) imports `infrastructure.observability.metrics`; belongs in observability.
- **Session lifecycle in worker**: queue/reindex repositories call `rollback()` after reads (`repositories.py:312,328,440`) implyi

### From devops-infra
- Verify the backend refuses default secrets (`NEXUS_SECRETS_KEY=change-me-in-local-env`, `nexus` DB password, `nexus-local` Qdrant key) when `APP_ENV` is not `local`; nothing in this segment enforces it (api-http / auth reviewers).
- `/metrics` exposure: `compose.yaml:11-12` publishes the backend port on all host interfaces, so the Nginx-only protection noted by another reviewer is bypassable at `host:8000/metrics` (api-http / auth).
- `CORS_ALLOWED_ORIGINS` (`.env.example:77`) must be kept manually in sync with `NEXUS_FRONTEND_URL` (`.env.example:68`): candidate for deriving one from the other in the config module.
- `API_HOST` / `API_PORT` (`.env.example:2-3`) are not used by the Dockerfile CMD (`backend.Dockerfile:32` hardcodes 0.0.0.0:8000); check whether the app config reads them.
- Table list in `backup-common.sh:15` is hardcoded; the database/migrations reviewer should confirm it covers all tables (e.g. ingestion job tables are not counted).
- `LLM_API_KEY` is absent from `.env

### From frontend-core-store
- Verify `app.routes.ts` applies `roleGuard()` to every route (guard coverage cannot be judged from this segment). `roleGuard` returns `false` on status "error" (`access.ts:23`), so the app shell must render `selectSessionError`, otherwise the user sees a blank page.
- Components in other segments call `nexusActions.stopDocumentPolling`; if a component forgets to dispatch it on destroy, polling continues while the same assistant stays active.
- `/config.json` (`auth.service.ts:12`) and nginx/CSP: no CSP is visible here; the markdown image-exfiltration finding below depends on `img-src`/`connect-src` policy set in the web server segment.
- Backend SSE framing: `chat-stream.ts:18` only splits on `\n\n`. If the API uses sse-starlette (default `\r\n`), parsing yields nothing. Backend reviewer should confirm separator.
- Backend 429/error body contracts (`usage_limit`, `duplicate_document`) are duplicated as TS interfaces here (`chat-stream.ts:82`, `document-lifecycle.ts:82`).

### From ingestion-and-worker
- **data segment**: claims use `FOR UPDATE SKIP LOCKED` (`infrastructure/database/repositories.py:308`, `:436`, grep-only) — good, but `IngestionJobQueue.complete/retry/fail` and `ReindexJobRepository.save` need an ownership/fencing check (`WHERE status='reserved' AND attempts=:n`) to make the findings below safe. Verify there.
- **data segment**: confirm a DB unique constraint on `(assistant_id, content_hash)`; `find_by_hash` (`ingest_document.py:112`) is check-then-act under concurrent uploads.
- **domain segment**: confirm `ReindexInProgressError` / `IndexOutdatedError` are not subclasses of `DomainValidationError`/`ValueError`; if `ReindexInProgressError` is, the D8 race path (`process_ingestion.py:294`) fails documents definitively instead of retrying.
- **api segment**: size limit is checked after the whole upload is in memory (`ingest_document.py:89` receives `bytes`); enforce streaming limit / `Content-Length` at the route. Also confirm `IngestDocumentInput.document_id` / `new_

### From rag-retrieval
- **LLM gateway (openai segment)**: `max_tokens`, `temperature`, timeout, retry/backoff and chunk delimiting (`<trecho>` tags implied by `prompt_injection.py:39`) all live in the adapter, not here. Verify: (a) `max_tokens` set; (b) chunk text escapes `</trecho>`; (c) exceptions are mapped to `ValueError/RuntimeError`, otherwise the rewrite fallback at `grounded_answer.py:124` does not catch timeouts.
- **API/DI segment**: lifetime of `ChatWithAssistantUseCase`. It holds per-request mutable state (`_ranked_so_far`, `_usage_so_far`, `chat_with_assistant.py:139-140`). Singleton = cross-user audit/usage contamination; per-request = 3 LangGraph compiles per request (`:141-143`).
- **API segment**: sync model inference + Qdrant calls must run in threadpool (`def` routes), not inside `async def` routes, or the event loop blocks.
- **API segment**: no question length cap here; `ChatWithAssistantInput.question` is unbounded (cost + rewrite prompt size).
- **Ingestion segment**: ACL is fail-open
