# Segment: database

**Reviewed by:** db-schema-reviewer

## Files reviewed
- `backend/src/infrastructure/database/alembic/env.py`
- `backend/src/infrastructure/database/alembic/versions/0001_baseline.py`
- `backend/src/infrastructure/database/alembic/versions/0002_semantic_retrieval.py`
- `backend/src/infrastructure/database/alembic/versions/0003_message_citations.py`
- `backend/src/infrastructure/database/alembic/versions/0004_access_control.py`
- `backend/src/infrastructure/database/alembic/versions/0005_document_lifecycle.py`
- `backend/src/infrastructure/database/alembic/versions/0006_operations.py`
- `backend/src/infrastructure/database/alembic/versions/0007_reindex_in_worker.py`
- `backend/src/infrastructure/database/base.py`
- `backend/src/infrastructure/database/migrate.py`
- `backend/src/infrastructure/database/models.py`
- `backend/src/infrastructure/database/operations_repositories.py`
- `backend/src/infrastructure/database/repositories.py`
- `backend/src/infrastructure/database/session.py`

## Integrations
- postgres
- sqlalchemy
- alembic

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `base.py` | `Base` | class | DeclarativeBase; no MetaData naming_convention |
| `session.py` | `engine` / `SessionLocal` | module globals | Engine built at import from `DATABASE_URL` env (default creds `nexus:nexus`) |
| `session.py` | `get_db_session` | function | FastAPI dependency: yields Session, closes in finally |
| `migrate.py` | `run_migrations` | function | Programmatic `alembic upgrade head` (no alembic.ini) |
| `alembic/env.py` | `run_migrations_online/offline` | function | Reuses app engine + `Base.metadata` |
| `models.py` | 13 ORM models | class | See Schema inventory |
| `repositories.py` | `PostgresAssistantRepository` | class | CRUD assistants; commits per call |
| `repositories.py` | `PostgresConversationRepository` | class | Conversations + messages; eager-loads all messages |
| `repositories.py` | `PostgresDocumentRepository` | class | Documents CRUD, hash lookup (RN-26) |
| `repositories.py` | `PostgresIngestionJobQueue` | class | Job queue on `ingestion_jobs` via `FOR UPDATE SKIP LOCKED` |
| `repositories.py` | `PostgresReindexJobRepository` | class | Reindex jobs; lease claim via `SKIP LOCKED` |
| `repositories.py` | `PostgresAssistantPermissionRepository` | class | Assistant/document group links (replace-all) |
| `repositories.py` | `PostgresAuditLogRepository` | class | Append + filtered/paginated listing of audit events |
| `repositories.py` | `PostgresAuditRetentionRepository` | class | Purge audit rows using `SET LOCAL nexus.audit_purge` |
| `repositories.py` | `PostgresSecretSettingsRepository` | class | Upsert/get encrypted secrets |
| `repositories.py` | `_write_document` / `_apply_job` | function | Model mutators without commit |
| `repositories.py` | `_*_to_entity`, `_citations_*_json` | function | Model -> domain mappers |
| `operations_repositories.py` | `PostgresUsageRecordRepository` | class | Append usage, aggregate by user/conversation |
| `operations_repositories.py` | `PostgresUsageLimiter` | class | RN-32 rate check over last N usage rows |
| `operations_repositories.py` | `PostgresUsageSettingsRepository` | class | Usage limits in `app_settings` |
| `operations_repositories.py` | `PostgresIndexParametersRepository` | class | BM25 params per collection in `app_settings` |
| `operations_repositories.py` | `PostgresFeedbackRepository` | class | Message feedback upsert/list |
| `operations_repositories.py` | `_sparse_key` | function | `bm25:` key, blake2b-hashed when > 64 chars |
| `operations_repositories.py` | `_aware` | function | Coerce naive datetimes to UTC |
| `operations_repositories.py` | `ingestion_job_gauges` | function | Prometheus gauge: ingestion jobs per status |

## Conventions observed
- **Naming**: snake_case columns; plural snake_case tables (outlier: `message_feedback`, uncountable); PascalCase `*Model` classes; `Postgres*Repository` classes.
- **Error handling**: mostly none — commit without try/rollback; only `PostgresIngestionJobQueue._write`, `PostgresAuditRetentionRepository.purge_older_than`, `PostgresReindexJobRepository.save` roll back. IntegrityError -> domain error only for reindex.
- **Logging**: none in this segment.
- **Async style**: synchronous SQLAlchemy 2.0 (`select()`, `Mapped[]`), sync psycopg.
- **Type hints**: mostly typed; untyped `_totals`, `_summary(row)`, `ingestion_job_gauges(session_factory)` in `operations_repositories.py:111,131,379`.
- **Timestamps**: all `DateTime(timezone=True)`, `*_at` suffix everywhere (`created_at`, `updated_at`, `occurred_at`, `reserved_at`, `lease_expires_at`) — consistent.
- **Soft delete**: none; hard delete everywhere. Document versioning via `status='substituido'` (REPLACED), "archive" = `conversations.owner_user_id IS NULL`.
- **Transactions**: every repository method commits its own unit of work.

## Internal duplication
- Upsert pattern `session.get -> add or mutate -> commit` repeated 7x: `repositories.py:52,99,365,595`, `operations_repositories.py:199,250,286`.
- `app_settings` upsert duplicated verbatim in `operations_repositories.py:199-217` and `:250-270`.
- Message ordering done twice: `relationship(order_by=MessageModel.created_at)` `models.py:202` and Python re-sort `repositories.py:634`.
- Partial-index predicate `status = 'running'` duplicated as raw literal in `models.py:260` and `0002_semantic_retrieval.py:84` (must match `ReindexStatus.RUNNING.value`).
- Grant/rollback-free "list + map" loops repeated across all list methods (acceptable).

## Cross-segment hints
- **Business rules inside repositories**: conversation auto-naming (truncate to 97 chars + "...") in `repositories.py:182-184`; "no ingestion while assistant reindexing" in `repositories.py:290-304`; "deleted document is not resurrected" (C4) in `repositories.py:352-354`. Belong in application/domain.
- **Transaction ownership**: repositories commit internally, so use cases cannot make multi-repo writes atomic (e.g. assistant save + `set_assistant_groups` + `audit.append`). Route to application segment: introduce Unit of Work.
- **Audit atomicity**: `PostgresAuditLogRepository.append` commits independently (`repositories.py:537`) — audited action and audit row can diverge. Route to auth/audit segment.
- **Metrics in DB layer**: `ingestion_job_gauges` (`operations_repositories.py:379`) imports `infrastructure.observability.metrics`; belongs in observability.
- **Session lifecycle in worker**: queue/reindex repositories call `rollback()` after reads (`repositories.py:312,328,440`) implying a long-lived worker session; worker segment should verify session-per-iteration and handle the un-rolled-back failures listed below.
- **Config**: hardcoded default DSN with credentials `session.py:9`; no `pool_pre_ping`/pool sizing `session.py:11`. Route to config/deploy segment.
- **Tests**: `_aware()` exists only in ops repositories, implying SQLite (naive datetimes) in tests; `repositories.py` mappers do not normalize — test/prod divergence risk.

## Specialist findings

### Schema inventory
| Table/Collection | File:Line | Key fields | Indexes | FKs | Soft delete? |
|------------------|-----------|------------|---------|-----|--------------|
| `assistants` | models.py:30 | id, name, initial_prompt, created_at | PK | — | no (hard) |
| `documents` | models.py:53 | id, assistant_id, content_hash, status, version, replaces_document_id, metadata_json(Text) | PK, (assistant_id, content_hash) | assistant_id->assistants CASCADE; replaces_document_id->documents SET NULL | no; versions via status |
| `ingestion_jobs` | models.py:130 | id, document_id, kind, status, available_at, reserved_at | PK, (document_id), (status, available_at) | document_id->documents CASCADE | no |
| `conversations` | models.py:169 | id, assistant_id, owner_user_id, updated_at | PK, (assistant_id), (owner_user_id) | assistant_id->assistants CASCADE | no; owner NULL = archived |
| `messages` | models.py:207 | id, conversation_id, role, content, citations(JSON) | PK, (conversation_id) | conversation_id->conversations CASCADE | no |
| `secret_settings` | models.py:235 | key_name, encrypted_value | PK | — | no |
| `reindex_jobs` | models.py:252 | id, assistant_id, status, attempts, lease_expires_at | PK, (assistant_id), UNIQUE(assistant_id) WHERE status='running' | assistant_id->assistants CASCADE | no |
| `assistant_groups` | models.py:308 | (assistant_id, group_name) | composite PK | assistant_id->assistants CASCADE | no |
| `document_groups` | models.py:321 | (document_id, group_name) | composite PK | document_id->documents CASCADE | no |
| `audit_events` | models.py:334 | id, occurred_at, user_id, action, resource_*, details(JSON) | PK, (occurred_at), (user_id), (action) | — (append-only trigger, 0004) | no; retention purge |
| `usage_records` | models.py:352 | id, user_id, conversation_id, assistant_id, tokens, estimated_cost, occurred_at | PK, (user_id, occurred_at), (occurred_at), (conversation_id) | conversation_id SET NULL; assistant_id SET NULL | no |
| `app_settings` | models.py:386 | key_name, value(JSON) | PK | — | no |
| `message_feedback` | models.py:399 | id, message_id, conversation_id, assistant_id, user_id, rating, status | PK, UNIQUE(message_id, user_id), (assistant_id, status) | assistant_id->assistants CASCADE (message/conversation intentionally no FK) | no |

### Migration linearity
- Linear chain 0001 -> 0007, single head, every revision has a `downgrade` — good.
- **med** — Destructive downgrades with no guard: `0004_access_control.py:103` drops `audit_events`, contradicting RN-25 immutability; `0005:98-109` drops document versions/jobs; `0002:91` drops reindex history. Add a refusal/guard on 0004 downgrade in production.
- **low** — `0001_baseline.py:131-136` downgrade unconditionally drops tables the upgrade may only have *adopted* (pre-existing `create_all` DBs).
- **low** — `0001_baseline.py:36-124` adoption path patches only `assistants.initial_prompt` and `conversations.name`; any other legacy shape difference (e.g. missing `ix_messages_conversation_id`) is silently accepted.
- **low** — `env.py:26-29` no `compare_type=True` / `compare_server_default=True`; autogenerate will not surface the drift below.

### Schema drift (models.py vs migrations)
- **low** — Server defaults exist in migrations but not models: `created_at`/`updated_at` `server_default=now()` (`0001:27`, `0002:68`) vs Python-only `default=_utc_now` (`models.py:37,73,180`); `documents.metadata_json` `server_default='{}'` (`0001:66`) vs Python default (`models.py:70`); `usage_records` token/cost/boolean `server_default` (`0006:52-63`) vs Python defaults (`models.py:376-382`); `message_feedback.out_of_scope` (`0006:109` vs `models.py:427`).
- **low** — Inconsistent server-default convention across migrations: 0001/0002 use `now()`; `ingestion_jobs.created_at` (`0005:83`), `app_settings.updated_at` (`0006:81`), `message_feedback.created_at/updated_at` (`0006:113-114`) have none -> raw SQL inserts fail.
- **low** — FK names: migrations name some FKs (`fk_documents_replaces_document_id` `0005:53`, `fk_usage_records_*` `0006:36,46`, `fk_message_feedback_assistant_id` `0006:94`) while 0001/0002/0004 rely on PG auto-names and `models.py` names none. `Base` has no `naming_convention` (`base.py:4`), so future `drop_constraint` calls must guess names.
- **low** — JSON storage drift: `documents.metadata_json` is `Text` with manual `json.dumps/loads` (`models.py:68`, `repositories.py:725,767`) while every other JSON column is `sa.JSON`.
- **low** — User identifier width drift: `owner_user_id`/`user_id`/`updated_by` `String(128)` vs `uploaded_by`/`reviewed_by` `String(255)` (`models.py:123,428`) — unclear whether those hold ids or display names.

### N+1 / unbounded queries
- **high** — `list_by_assistant` (`repositories.py:134-152`) and `list_archived` (`:154-165`) `selectinload` *every message of every conversation* with no LIMIT/pagination, only to render a list. Payload grows O(total messages per user); `list_archived` loads all legacy history across all users.
- **med** — `PostgresConversationRepository.save` (`repositories.py:118`) re-runs `get_by_id`, reloading the full message history after each save.
- **med** — Assistant delete (`repositories.py:86-92`) uses ORM cascade (`models.py:43-50`, `200-204`) without `passive_deletes=True`: SQLAlchemy loads all conversations, then lazily each conversation's messages (N+1), then all documents, deleting row by row — DB `ON DELETE CASCADE` already does this. Same for conversation delete (`repositories.py:202-208`).
- **med** — Unbounded lists: `list_messages` (`repositories.py:188`), `PostgresDocumentRepository.list_by_assistant` (`:229`), `list_document_groups` (`:491`), `list_assistant_groups` (`:462`), `list_expired` (`:319`), `list_running` (`:414`).
- **low** — `expire_on_commit=True` default (`session.py:12`): `save_message` maps the model after commit (`repositories.py:185-186`) triggering a re-SELECT; `save` methods also call explicit `refresh` (`:68,222,389,446`).

### Index gaps
- **med** — `conversations` listing filters `(assistant_id, owner_user_id)` ordered by `updated_at DESC` (`repositories.py:142-147`) but only single-column indexes exist (`0001:86`, `0004:65`). Add `(owner_user_id, assistant_id, updated_at DESC)`.
- **med** — `audit_events` filter on `details->>'assistant_id'` (`repositories.py:546-550`) on a `json` (not `jsonb`) column: seq scan, not indexable by GIN. Also no composite `(user_id, occurred_at)` / `(action, occurred_at)` for the filtered+sorted+OFFSET listing (`:555-559`).
- **med** — `usage_records.assistant_id` FK unindexed (`models.py:370`, `0006:41`): `ON DELETE SET NULL` on assistant delete scans the whole table.
- **low** — `documents.replaces_document_id` self-FK unindexed (`models.py:118`, `0005:46`): each document delete scans `documents` for SET NULL.
- **low** — `messages` ordered by `created_at` within conversation (`repositories.py:195`, `models.py:202`) with index on `conversation_id` only; prefer `(conversation_id, created_at)`.
- **low** — `message_feedback` listing sorts by `updated_at DESC` with optional `rating`/`status` filters (`operations_repositories.py:310-321`); global (admin) listing has no supporting index. `conversation_id` unindexed (`models.py:412`).
- **low** — `reindex_jobs.claim_next` filters `status` + `lease_expires_at` (`repositories.py:426-436`); no status index (table small; acceptable).
- OK: limiter uses `(user_id, occurred_at)` (`operations_repositories.py:172-180`); queue uses `(status, available_at)`; `find_by_hash` uses `(assistant_id, content_hash)`.

### Raw SQL leakage
- None exploitable. `text()` only with constant `SET LOCAL nexus.audit_purge = 'on'` (`repositories.py:573,580`); migration `op.execute` strings are static (`0004:26-96`). JSON path filter is bound (`repositories.py:548`).

### Transaction boundaries
- **high** — No rollback on commit failure in most write paths (`repositories.py:67,91,117,185,221,286,483,516,537,614`; `operations_repositories.py:64,216,270,292`). A failed flush leaves the Session in "inactive transaction" state; any long-lived session (worker) is poisoned until rollback.
- **med** — `PostgresFeedbackRepository.save` (`operations_repositories.py:286-293`): concurrent first-time feedback for the same `(message_id, user_id)` hits `uq_message_feedback_message_user` -> unhandled `IntegrityError` (500) instead of upsert/domain error. Same pattern for `PostgresSecretSettingsRepository` / settings upserts (PK race) — use `INSERT ... ON CONFLICT`.
- **med** — `set_assistant_groups`/`set_document_groups` (`repositories.py:469-516`) are atomic per call, but group change + audit + entity save are separate commits (see cross-segment hint).
- **med** — RN-26 duplicate detection is app-side only (`0005:7-9`, `repositories.py:244-260`): concurrent uploads of the same file both pass. A partial unique index `(assistant_id, content_hash) WHERE status <> 'substituido'` after deduping legacy rows closes it.
- **low** — `PostgresUsageLimiter` race acknowledged in docstring (`operations_repositories.py:156-157`); acceptable but documented-only.
- Good: queue `_write` job+documents single transaction with rollback (`repositories.py:346-358`); `SKIP LOCKED` reservation (`:308`, `:436`); purge scoped by `SET LOCAL` (`:578-588`).

### Cascade / ON DELETE
- **med** — Retention semantics inconsistent on assistant delete: `usage_records` survive (`SET NULL`, `0006:44-48`) but `message_feedback` including curated expected answers are wiped (`CASCADE`, `0006:92-96`). Decide whether curator data should outlive the assistant.
- **low** — `message_feedback.message_id`/`conversation_id` intentionally have no FK (`0006:7-8`); deleting a conversation leaves feedback pointing at non-existent ids — consumers must tolerate dangling refs.
- **low** — ORM `cascade="all, delete-orphan"` duplicates DB `ON DELETE CASCADE` (`models.py:43-50,200-204`); add `passive_deletes=True`.

### Enum / constraint consistency
- **med** — No CHECK constraints on any enum-like column: `documents.status` (`models.py:98`), `ingestion_jobs.kind/status` (`:145-146`), `reindex_jobs.status` (`:272`), `messages.role` (`:217`), `message_feedback.rating/status` (`:419,424`). A bad value written by SQL/another service makes mappers raise `ValueError` on read (`repositories.py:670,756-757,779,798`; `operations_repositories.py:347,361`).
- **low** — `uq_reindex_jobs_running` hard-codes `'running'` (`models.py:260`, `0002:84`); renaming `ReindexStatus.RUNNING` silently breaks the one-running-job guarantee.
- **low** — No CHECK for non-negative counters (`attempts`, `chunk_count`, token counts, `estimated_cost`).
- **low** — `0005:30-34` default `'indexado'` and `models.py:100` duplicate `DocumentStatus` value as literal.

### Timestamp / timezone handling
- All columns `timestamptz` — good. Python defaults use `datetime.now(UTC)` (`models.py:26-27`).
- **low** — Normalization inconsistent: `operations_repositories.py:375` `_aware` applied to feedback/limiter only; `repositories.py` mappers pass raw values. Harmless on PG, divergent on SQLite tests.

### Soft delete / naming
- Hard delete everywhere — consistent. Archive/versioning are status-based (documented).
- Tables plural snake_case (outlier `message_feedback`), columns snake_case — consistent.

## Concerns / smells
1. **high** — Conversation listings eager-load every message with no pagination (`repositories.py:134-165`); will degrade linearly with chat history.
2. **high** — Missing rollback on failed commits across ~14 write paths; long-lived worker sessions get poisoned (`repositories.py`, `operations_repositories.py`).
3. **med** — Repositories own commits: no Unit of Work, so audit + action + group changes are not atomic; audit trail can diverge from reality.
4. **med** — Index gaps on hot paths: conversation listing composite, audit `details->>'assistant_id'` on `json`, `usage_records.assistant_id` FK.
5. **med** — No CHECK constraints for enum-like status columns; ORM cascades without `passive_deletes` cause N+1 deletes.

## Refactor suggestions
1. `repositories.py:134-165` — Add `list_summaries(assistant_id, owner, limit, cursor)` that selects conversation columns only (plus optional last-message subquery); drop `selectinload(messages)` from listings; keep full load for `get_by_id`.
2. `models.py:43-50,200-204` — Add `passive_deletes=True` to cascade relationships; delete via `delete(Model).where(...)` so PG `ON DELETE CASCADE` does the work.
3. New migration `0008` — Indexes: `conversations(owner_user_id, assistant_id, updated_at DESC)`, `messages(conversation_id, created_at)`, `usage_records(assistant_id)`, `documents(replaces_document_id)`, `audit_events(user_id, occurred_at)`; convert `audit_events.details` to `jsonb` + expression index on `(details->>'assistant_id')`; CHECK constraints for status/role/rating columns. Mirror in `models.py`.
4. `base.py:4` — Set `MetaData(naming_convention=...)` and `env.py:26` `compare_type=True, compare_server_default=True`; align `server_default`s in `models.py` with migrations so autogenerate is clean.
5. `repositories.py` / `operations_repositories.py` — Extract a `_commit()` helper (commit, rollback on exception, map `IntegrityError`) and move toward a Unit of Work where the application layer commits; replace settings/feedback/secret upserts with `postgresql.insert(...).on_conflict_do_update`.
