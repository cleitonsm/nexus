# Segment: api-http

**Reviewed by:** backend-api-reviewer

## Files reviewed
- `backend/src/api/dependencies.py`
- `backend/src/api/errors.py`
- `backend/src/api/main.py`
- `backend/src/api/middleware.py`
- `backend/src/api/routes/admin.py`
- `backend/src/api/routes/assistants.py`
- `backend/src/api/routes/conversations.py`
- `backend/src/api/routes/documents.py`
- `backend/src/api/routes/feedback.py`
- `backend/src/api/routes/index.py`
- `backend/src/api/routes/me.py`
- `backend/src/api/schemas/access.py`
- `backend/src/api/schemas/admin.py`
- `backend/src/api/schemas/assistants.py`
- `backend/src/api/schemas/conversations.py`
- `backend/src/api/schemas/index.py`
- `backend/src/api/schemas/operations.py`
- (context only: `routes/__init__.py`, `schemas/__init__.py`; `requirements.txt` pins fastapi==0.115.12)

## Integrations
- fastapi (0.115.12) / starlette
- Keycloak (via `TokenVerifier`, `GroupDirectory`)
- PostgreSQL (SQLAlchemy sessions via `get_db_session`)
- Qdrant (`QdrantVectorStoreGateway`)
- OpenAI-compatible LLM HTTP API (`HttpChatCompletionsLLM`)
- Prometheus text exposition (`/metrics`)

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `main.py` | `lifespan` | async ctx manager | runs migrations + sparse-param check before serving |
| `main.py` | `app` | FastAPI | app, CORS, error handlers, 9 routers; docs only when `api_docs_enabled()` |
| `main.py` | `health` | route | GET /health, static `{"status":"ok"}`, no auth |
| `main.py` | `metrics` | route | GET /metrics Prometheus text, no auth, hidden from schema |
| `main.py` | `_report_sparse_parameter_changes` | function | best-effort BM25 drift warning at startup |
| `dependencies.py` | `get_current_user` | dependency | Bearer parse + `TokenVerifier.verify`, 401 with WWW-Authenticate |
| `dependencies.py` | `get_*_repository` (x14) | dependencies | build Postgres repos over the request session |
| `dependencies.py` | `get_vector_store_gateway` | dependency | new Qdrant gateway per call from env |
| `dependencies.py` | `get_secret_cipher` | dependency | Fernet cipher from `NEXUS_SECRETS_KEY` (default "") |
| `dependencies.py` | `build_llm_gateway` | function | decrypt key per request, return traced LLM or Unconfigured stub |
| `dependencies.py` | `UnconfiguredLLMGateway` | class | LLM stub raising `ValueError` when key/model missing |
| `dependencies.py` | `build_context_retriever` | function | wires embedding/sparse/rerank/vector store retriever |
| `dependencies.py` | `build_usage_governance` | function | wires rate limiter + usage records |
| `errors.py` | `register_error_handlers` | function | 403/503/429/409 handlers for 4 domain errors |
| `errors.py` | `usage_limit_response` | function | 429 envelope with Retry-After + retry metadata |
| `middleware.py` | `register_request_context` | function | X-Request-ID binding, root span, HTTP metrics, access log |
| `middleware.py` | `_route` / `_record` / `_request_fields` | helpers | route template label, metric emit, log fields |
| `routes/admin.py` | 7 handlers | routes | API key, LLM test, usage report/limits, audit events |
| `routes/assistants.py` | 6 handlers | routes | assistant CRUD-ish, infer, groups, conversation list |
| `routes/conversations.py` | 6 + 3 handlers | routes | conversations, messages, chat, SSE chat; archived (admin) |
| `routes/conversations.py` | `_server_sent_events` / `_in_one_context` / `_sse` | helpers | SSE framing, contextvar-preserving iteration, error event |
| `routes/conversations.py` | `_chat_error` | helper | maps chat exceptions to 404/409/422/502 |
| `routes/documents.py` | 7 handlers | routes | upload, list, get, delete, replace, reprocess, groups |
| `routes/documents.py` | `_translate_errors` | ctx manager | document domain errors -> 409/404/413/422 |
| `routes/documents.py` | `_parse_groups_field` / `_parse_metadata_field` | helpers | manual JSON parsing of multipart form fields |
| `routes/feedback.py` | 4 handlers | routes | submit, list, review, JSONL export |
| `routes/index.py` | `start_reindex` / `get_index_status` | routes | enqueue reindex, index health |
| `routes/index.py` | `_existing_assistant_id` | helper | id parse + existence 404 |
| `routes/me.py` | `get_me` / `list_groups` | routes | identity from token, Keycloak group directory |
| `schemas/*.py` | 30 Pydantic models | classes | request/response DTOs (Pydantic v2) |

## Conventions observed
- **Naming**: snake_case functions/fields, PascalCase models; URL paths kebab-case (`/api-key`, `/usage-limits`, `/audit-events`, `/index-status`, `/archived-conversations`); plural collection nouns.
- **Error handling**: use cases raise domain exceptions; routes translate with per-handler `try/except -> HTTPException`; 4 global handlers in `errors.py:16`; documents use a shared `_translate_errors` ctx manager (`documents.py:306`).
- **Logging**: stdlib `logging` with event-name messages (`"chat.stream.failed"`) + `extra={}` structured fields.
- **Async style**: sync `def` handlers (threadpool) everywhere except `ingest_document` and `replace_document` (async, offload use case via `run_in_threadpool`).
- **Type hints**: fully typed; several deps annotated with concrete infra classes (`PostgresAssistantRepository`) instead of domain ports.

## Internal duplication
- `DomainValidationError -> 422` try/except block repeated ~15 times (`admin.py:205,262,323`, `assistants.py:87,157,193,223`, `conversations.py:118,136,164,202,236,485,524`, `feedback.py:80,140`); only documents centralise it.
- "Parse AssistantId + get_by_id + 404" repeated 5x: `conversations.py:116-129`, `assistants.py:221-234`, `documents.py:110-115`, `documents.py:159-164`, `index.py:49-65`.
- `ConversationResponse` and `ConversationHistoryResponse` are field-identical (`schemas/conversations.py:13` vs `:22`).
- Conversation detail mapping duplicated (`conversations.py:172-183` vs `:495-506`).
- `ChatWithAssistantUseCase(...)` 9-arg construction duplicated (`conversations.py:269-279` vs `:319-329`).
- LLM URL default `os.getenv("LLM_API_URL", "https://api.openai.com/...")` duplicated (`admin.py:137` vs `dependencies.py:306`).
- Mapping by explicit field copy vs `**asdict(dto)` mixed (`conversations.py:470`, `index.py:69` vs everywhere else).

## Cross-segment hints
- **auth/access**: no role is declared at the HTTP layer; all role checks live in `AccessControl` inside use cases. Auth segment must confirm every use case invoked here calls `AccessControl` (esp. `InferAssistantUseCase`, which receives no `access_control`, `assistants.py:119`).
- **config**: `get_secret_cipher` defaults `NEXUS_SECRETS_KEY` to `""` (`dependencies.py:178`) — config segment must confirm Fernet fails closed.
- **config/deploy**: `/metrics` is protected only by Nginx returning 404 (`main.py:105`); verify the backend container port is not published in compose/k8s.
- **config**: `cors_allowed_origins()` contents not visible here; verify no `*` in prod.
- **data**: `get_db_session` commit/rollback semantics determine whether SSE writes persist after dependency teardown (see SSE finding).
- **infrastructure/llm**: `HttpChatCompletionsLLM` exception messages are echoed to clients (`admin.py:170`, `conversations.py:368`); confirm they never include upstream bodies or the API key.
- **storage**: `file.filename` passed raw as `source_name` (`documents.py:140,246`) — storage segment must sanitise for path use.
- **application**: `test_api_key` logic (`admin.py:113-178`) should become a `TestGlobalApiKeyUseCase`.

## Specialist findings

### Endpoint inventory
39 routes in code (static index listed 32 + a test-only `/ping`; it missed the `""`-path routes). Auth = `get_current_user` (router-level + handler param). Role = enforced inside the use case via `AccessControl`; expected role taken from docstrings/tests (`Role.ADMIN/CURATOR/USER`).

| Method | Path | File:Line | Auth | Role (use case) | Request | Response | Notes |
|--------|------|-----------|------|-----------------|---------|----------|-------|
| GET | /health | main.py:91 | no | — | — | dict | liveness only, no dep checks |
| GET | /metrics | main.py:101 | **no** | — | — | text/plain | relies on Nginx 404 |
| GET | /admin/api-key/status | admin.py:67 | yes | admin | — | ApiKeyStatusResponse | — |
| POST | /admin/api-key | admin.py:82 | yes | admin | SaveApiKeyRequest | ApiKeyStatusResponse 201 | upsert; no max_length |
| POST | /admin/api-key/test | admin.py:113 | yes | admin | — | ApiKeyTestResponse | business logic in route |
| GET | /admin/usage | admin.py:181 | yes | admin | query from/to/limit<=500 | UsageReportResponse | — |
| GET | /admin/usage-limits | admin.py:224 | yes | admin | — | UsageLimitsResponse | — |
| PUT | /admin/usage-limits | admin.py:241 | yes | admin | UsageLimitsRequest | UsageLimitsResponse | bounded ints |
| GET | /admin/audit-events | admin.py:292 | yes | admin | query filters, limit<=200, offset | list[AuditEventResponse] | paged |
| GET | /admin/archived-conversations | conversations.py:463 | yes | admin | — | list[ConversationResponse] | unpaged |
| GET | /admin/archived-conversations/{id} | conversations.py:473 | yes | admin | — | ConversationDetailResponse | — |
| DELETE | /admin/archived-conversations/{id} | conversations.py:509 | yes | admin | — | 204 | — |
| POST | /assistants | assistants.py:68 | yes | admin | CreateAssistantRequest | AssistantResponse 201 | description/prompt unbounded |
| GET | /assistants | assistants.py:95 | yes | any (filtered) | — | list[AssistantResponse] | unpaged |
| POST | /assistants/infer | assistants.py:107 | yes | any | InferAssistantRequest | InferAssistantResponse | question unbounded; LLM call |
| DELETE | /assistants/{assistant_id} | assistants.py:136 | yes | admin | — | 204 | — |
| PUT | /assistants/{assistant_id}/groups | assistants.py:170 | yes | admin | GroupsRequest | GroupsResponse | — |
| GET | /assistants/{assistant_id}/conversations | assistants.py:206 | yes | owner | — | list[ConversationHistoryResponse] | 404 before authz; unpaged |
| POST | /assistants/{assistant_id}/documents | documents.py:85 | yes | admin/curator | multipart file+metadata+groups | DocumentAccessResponse 202 | unbounded read; 404 before authz |
| GET | /assistants/{assistant_id}/documents | documents.py:150 | yes | admin/curator | — | list[DocumentAccessResponse] | unpaged; 404 before authz |
| POST | /assistants/{assistant_id}/reindex | index.py:72 | yes | admin | — | ReindexJobResponse 202 | 404 before authz |
| GET | /assistants/{assistant_id}/index-status | index.py:108 | yes | admin | — | IndexStatusResponse | 404 before authz |
| GET | /documents/{document_id} | documents.py:172 | yes | admin/curator | — | DocumentAccessResponse | — |
| DELETE | /documents/{document_id} | documents.py:188 | yes | admin/curator | — | 204 | no `response_class=Response` |
| PUT | /documents/{document_id}/content | documents.py:212 | yes | admin/curator | multipart file | DocumentAccessResponse 202 | unbounded read |
| POST | /documents/{document_id}/reprocess | documents.py:254 | yes | admin/curator | — | DocumentAccessResponse 202 | — |
| PUT | /documents/{document_id}/groups | documents.py:276 | yes | admin/curator | GroupsRequest | DocumentAccessResponse | — |
| POST | /conversations | conversations.py:100 | yes | any w/ assistant access | CreateConversationRequest | ConversationResponse 201 | 404 before authz |
| GET | /conversations/{conversation_id} | conversations.py:151 | yes | owner | — | ConversationDetailResponse | 404 for foreign (RN-24) |
| DELETE | /conversations/{conversation_id} | conversations.py:186 | yes | owner | — | 204 | — |
| POST | /conversations/{conversation_id}/messages | conversations.py:212 | yes | owner | AddMessageRequest | MessageResponse 201 | **accepts role=assistant/system** |
| POST | /conversations/{conversation_id}/chat | conversations.py:245 | yes | owner | ChatRequest | ChatResponse 201 | question unbounded |
| POST | /conversations/{conversation_id}/chat/stream | conversations.py:287 | yes | owner | ChatRequest | text/event-stream | SSE |
| POST | /messages/{message_id}/feedback | feedback.py:46 | yes | owner | SubmitFeedbackRequest | FeedbackResponse 201 | bounded comment |
| GET | /feedback | feedback.py:85 | yes | curator | query assistant_id/status/limit<=200/offset | list[FeedbackResponse] | paged |
| POST | /feedback/{feedback_id}/review | feedback.py:115 | yes | curator | ReviewFeedbackRequest | FeedbackResponse | — |
| GET | /feedback/export | feedback.py:145 | yes | curator | query assistant_id | application/x-ndjson | unbounded; raw id in header |
| GET | /me | me.py:21 | yes | any | — | CurrentUserResponse | — |
| GET | /groups | me.py:36 | yes | admin/curator | — | list[str] | 503 on Keycloak down |

### Auth posture
- All 37 business routes require a Bearer token (router-level `dependencies=[Depends(get_current_user)]` on every router). No unprotected mutating endpoint. **OK.**
- Roles are never expressed at the HTTP layer; correctness depends 100% on each use case calling `AccessControl`. `InferAssistantUseCase` (`assistants.py:119`) gets no access control; safe only because the candidate list is pre-filtered by `ListAssistantsUseCase` in the route. **med** (fragile contract).
- Existence oracle: assistant lookup + 404 runs **before** authorization in 6 routes (`conversations.py:124`, `assistants.py:229`, `documents.py:111`, `documents.py:160`, `index.py:60` x2 callers). An unauthorized user gets 404 vs 403 and can enumerate assistant IDs; contradicts the RN-24 "404 for foreign == nonexistent" rule applied to conversations. **med**
- `/metrics` unauthenticated in-app (`main.py:101`); protection is network topology only. Exposes route templates, status counts, ingestion job gauges. **med**
- `/docs`, `/redoc`, `/openapi.json` gated by `api_docs_enabled()` (`main.py:62-70`). OK.
- `/health` returns a static body, no leak. OK.

### Validation and size limits
- Upload bodies fully buffered with `await file.read()` (`documents.py:116`, `:230`) before `max_file_bytes` is enforced inside the use case. No `Content-Length` precheck or streamed cap: a multi-GB upload is held in memory per request. **high**
- Free-text fields with no `max_length`: `ChatRequest.question` (`schemas/conversations.py:65`), `InferAssistantRequest.question` (`schemas/assistants.py:15`), `AddMessageRequest.content` (`schemas/conversations.py:39`), `CreateAssistantRequest.description/initial_prompt` (`schemas/assistants.py:10-11`), `SaveApiKeyRequest.api_key` (`schemas/admin.py:5`). Unbounded prompts go straight to the LLM (cost) and DB. **med**
- `AddMessageRequest.role` allows `assistant` and `system` (`schemas/conversations.py:31-34`); a user can forge assistant/system turns in their own history, which then feed later LLM prompts (history poisoning / prompt injection). Tests only use `role="user"` (`tests/integration/test_access_control_api.py:433`). **high**
- `GroupsRequest.groups` caps list at 100 but not item length (`schemas/access.py:18`). **low**
- Multipart `metadata`/`groups` are `str` form fields parsed by hand (`documents.py:375-399`) instead of a typed model; metadata values coerced with `str()`, no key/value count or length cap. **low**
- Path IDs typed `str`; validated only in domain value objects. Acceptable, but OpenAPI advertises no format. **low**

### Pagination / filtering
- Paged: `/admin/audit-events`, `/feedback` (`limit`+`offset`, caps 200); `/admin/usage` (`limit` only, cap 500).
- Unpaged list endpoints: `GET /assistants`, `/assistants/{id}/conversations`, `/assistants/{id}/documents`, `/admin/archived-conversations`, `/feedback/export`. Conversation history grows unbounded per user. **med**
- Date filters use `from`/`to` aliases consistently (`admin.py:183-184`, `:297-298`). OK.

### Status codes
- `ValueError -> 422` in `_chat_error` (`conversations.py:363`) also catches `UnconfiguredLLMGateway`'s `ValueError` (`dependencies.py:279-285`): a server misconfiguration (no API key) is reported to end users as 422 client error. Should be 503. **med**
- `RuntimeError -> 502` with `detail=str(exc)` (`conversations.py:368`, `admin.py:170`) echoes upstream/internal messages to clients. **med**
- `_translate_errors` maps bare `ValueError -> 422` (`documents.py:340`): any internal bug raising `ValueError` becomes a 422. **low**
- `POST /admin/api-key` returns 201 on every save though it is an idempotent upsert (`admin.py:85`); PUT/200 fits. **low**
- Non-stream chat returns 201, stream returns 200 for the same operation (`conversations.py:248` vs `:287`). **low**
- 404 paths exist for assistant, conversation, document, feedback, message. OK.

### Error envelopes
- Majority: `{"detail": "<string>"}` (HTTPException + `errors.py` handlers).
- Outliers: 429 `{"detail","code","window","limit","retry_at","retry_after_seconds"}` (`errors.py:57-64`); 409 duplicate document `{"detail": {"code","message","document_id","source_name"}}` (`documents.py:314-319`, object nested in `detail`); FastAPI 422 validation `{"detail": [ {loc,msg,type} ]}` (list); SSE `event: error` `{"status","detail"}` (`conversations.py:410-416`). Clients must handle `detail` as string, object, or array. **med**
- Messages mixed language: English (`"assistant not found"`) and Portuguese (`"Limite de perguntas atingido."`, `admin.py:170`). **low**

### Streaming (SSE)
- Framing correct (`event:`/`data:` + blank line, `conversations.py:421`); `Cache-Control: no-cache`, `X-Accel-Buffering: no` set. Pre-stream errors return real HTTP status (`conversations.py:330-333`). OK.
- Session lifecycle: on FastAPI 0.115 yield-dependency teardown (`get_session`) runs **before** the streaming body is sent, so the generator keeps using a session that `get_db_session` already exited; SQLAlchemy silently reopens it, and the extra `session.close()` (`conversations.py:418`) is the only cleanup. Any commit-on-exit in `get_db_session` does not cover writes made during the stream. **med**
- Mid-stream exceptions other than `ValueError/RuntimeError` (e.g. `ConversationNotFoundError`, `IndexOutdatedError`) are reported as `{"status":500,"detail":"internal error"}` (`conversations.py:405`), unlike the pre-stream path. **low**
- No heartbeat comments during retrieval/rerank before first `delta`; long pre-generation phases risk proxy idle timeouts. **low**
- `@app.middleware("http")` (BaseHTTPMiddleware, `middleware.py:39`) closes the root span and records duration when headers are returned, not when the stream ends; SSE latency metrics/traces under-report. **low**

### Business logic in routes
- `test_api_key` (`admin.py:113-178`): authorization, key decryption, infra gateway construction (`HttpChatCompletionsLLM`), audit write, LLM call, error translation — a whole use case in the handler. Audit is written before the call regardless of outcome. **med**
- `infer_assistant` composes two use cases and hand-builds dicts (`assistants.py:118-132`). **low**
- `get_archived_conversation` instantiates `GetConversationUseCase` only to call `removed_sources` (`conversations.py:492-494`). **low**
- `export_feedback` builds JSONL serialization in the route (`feedback.py:157-170`). **low**
- Assistant existence checks (5 sites, see duplication) belong in the use cases, which would also fix the authz ordering.

### Sync blocking in async handlers
- `ingest_document` is `async def` and calls `assistant_repository.get_by_id` (sync SQLAlchemy) directly on the event loop (`documents.py:111`). Blocks all requests on that worker for the DB round-trip. **med**
- `replace_document` correctly offloads (`documents.py:241`). Other handlers are sync `def` (threadpool). OK.
- `lifespan` runs `run_migrations()` and the sparse check synchronously (`main.py:54-56`); startup only. **low**

### CORS
- Explicit methods/headers, `allow_credentials` default False, exposes `X-Request-ID`/`Retry-After` (`main.py:73-79`). Origins from `cors_allowed_origins()` (not visible). OK.

### REST hygiene
- No API version prefix on any route (`/assistants`, `/admin/...`). **low**
- RPC-style action paths: `POST /assistants/infer`, `POST /admin/api-key/test`, `POST /feedback/{id}/review`, `POST /documents/{id}/reprocess`, `POST /assistants/{id}/reindex`. Acceptable as commands, but `/feedback` and `/messages/{id}/feedback` live on a prefix-less router (`feedback.py:43`) unlike every other router. **low**
- Path casing consistent (kebab-case, plural nouns). OK.
- Side effects in GET: none observed in handlers.

### Other
- `get_vector_store_gateway` builds a new Qdrant client per request (`dependencies.py:236-239`); `get_llm_gateway` decrypts the key and logs per request (`dependencies.py:308`). **low** (perf)
- `usage_governance: UsageGovernance | None` (`conversations.py:264,307`) — dependency never returns None. **low**
- Unhandled exceptions bypass `response.headers[X-Request-ID]` (`middleware.py:59-65`), so 500s lack the correlation header. **low**

## Concerns / smells
1. **high** — Unbounded upload buffering: `await file.read()` before size enforcement (`documents.py:116`, `:230`) enables memory exhaustion.
2. **high** — `POST /conversations/{id}/messages` lets clients write `assistant`/`system` turns (`schemas/conversations.py:31-34`), poisoning history fed to the LLM.
3. **med** — Assistant existence 404 checked before authorization in 6 routes, giving an ID-enumeration oracle and contradicting RN-24.
4. **med** — Error mapping leaks/misclassifies: `ValueError->422` for missing LLM config, `RuntimeError->502` with raw `str(exc)`; four different error envelope shapes.
5. **med** — No length caps on chat/infer questions and assistant prompts; several list endpoints unpaged; `/metrics` unauthenticated in-app.

## Refactor suggestions
1. `routes/documents.py:116,230` — check `request.headers["content-length"]` and read `UploadFile` in chunks up to `max_file_bytes + 1`, returning 413 early; move `get_by_id` (`:111`) into the threadpool call or the use case.
2. `schemas/conversations.py:31-39` — restrict `AddMessageRequest.role` to `user` (or drop the route if unused by the UI); add `max_length` to `ChatRequest.question`, `InferAssistantRequest.question`, `CreateAssistantRequest.*`, `SaveApiKeyRequest.api_key`.
3. `api/errors.py` — register global handlers for `DomainValidationError` (422), `*NotFoundError` (404), `IndexOutdatedError`/`ReindexInProgressError` (409), and an `LLMNotConfiguredError` (503); delete the ~15 per-route try/except blocks and the bare `ValueError`/`RuntimeError` catches; standardise on one envelope `{detail, code}`.
4. `routes/{conversations,assistants,documents,index}.py` — move assistant existence checks into the use cases after `AccessControl` (return 404 for both missing and forbidden), removing `_existing_assistant_id` and its copies.
5. `routes/admin.py:113-178` — extract `TestGlobalApiKeyUseCase` taking an `LLMGatewayFactory` port; reuse `build_llm_gateway` so `LLM_API_URL` is read in one place; audit after the outcome with success/failure.
