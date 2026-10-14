# Segment: ingestion-and-worker

**Reviewed by:** queue-worker-reviewer

## Files reviewed
- `backend/src/application/services/document_indexing.py`
- `backend/src/application/services/index_state.py`
- `backend/src/application/services/ingestion.py`
- `backend/src/application/use_cases/ingest_document.py`
- `backend/src/application/use_cases/process_ingestion.py`
- `backend/src/application/use_cases/reindex_assistant.py`
- `backend/src/cli/check_consistency.py`
- `backend/src/cli/purge_audit.py`
- `backend/src/cli/worker.py`
- `backend/src/domain/chunking.py`
- `backend/src/infrastructure/chunking/sentences.py`
- `backend/src/infrastructure/chunking/structural_chunker.py`
- `backend/src/infrastructure/documents/extractor.py`
- `backend/src/infrastructure/documents/ocr.py`
- `backend/src/infrastructure/documents/structured_extraction.py`
- `backend/src/infrastructure/documents/text_extraction.py`
- `backend/src/infrastructure/storage/local_file_storage.py`

## Integrations
- filesystem (local original storage, temp dirs for OCR / .doc conversion)
- worker (polling CLI process over Postgres-backed queues)
- postgres (`ingestion_jobs`, `reindex_jobs`, documents, audit)
- qdrant (versioned collections + alias, point upsert/delete/activate)
- subprocess tools: pdftoppm, tesseract, antiword, catdoc, soffice

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `application/services/document_indexing.py` | `PIPELINE_VERSION` | const | pipeline version that forces reindex when bumped |
| `application/services/document_indexing.py` | `hash_content` | function | sha256 hex of raw bytes |
| `application/services/document_indexing.py` | `DocumentIndexer` | class | extract -> chunk -> dense+sparse embed -> VectorChunk list |
| `application/services/index_state.py` | `IndexState` | dataclass | alias/current/legacy collection state; computes next version |
| `application/services/index_state.py` | `read_index_state` | function | resolves alias and legacy flag from Qdrant |
| `application/services/index_state.py` | `is_index_outdated` | function | legacy or any indexed doc with other model/pipeline |
| `application/services/index_state.py` | `check_sparse_parameters` / `record_sparse_parameters` | function | BM25 param drift check / record |
| `application/services/ingestion.py` | `IngestionSettings` | dataclass | max_attempts=3, delays (30,120), job_timeout=600s |
| `application/services/ingestion.py` | `JobTimeoutError`, `*_REASON`, `WORKER_USER` | consts | failure reasons and worker identity |
| `application/use_cases/ingest_document.py` | `_DocumentIntake` | class | validate size/type/index/hash; save file, doc, groups, job |
| `application/use_cases/ingest_document.py` | `IngestDocumentUseCase` | class | RF-48 upload -> pending document + job |
| `application/use_cases/ingest_document.py` | `ReplaceDocumentUseCase` | class | RF-51 new version linked to previous |
| `application/use_cases/ingest_document.py` | `ReprocessDocumentUseCase` | class | RF-54 re-enqueue failed document |
| `application/use_cases/process_ingestion.py` | `_IngestionFailures` | class | retry-vs-fail decision, cleanup, audit |
| `application/use_cases/process_ingestion.py` | `ProcessNextIngestionJobUseCase` | class | reserve job, index inactive, activate, complete |
| `application/use_cases/process_ingestion.py` | `RequeueExpiredIngestionJobsUseCase` | class | expired reserved jobs -> retry/fail as timeout |
| `application/use_cases/reindex_assistant.py` | `StartReindexUseCase` | class | registers reindex job (API side) |
| `application/use_cases/reindex_assistant.py` | `RunReindexUseCase` | class | build next collection, verify count, swap alias |
| `application/use_cases/reindex_assistant.py` | `ProcessNextReindexJobUseCase` | class | claim reindex with lease; abandon after max attempts |
| `application/use_cases/reindex_assistant.py` | `GetIndexStatusUseCase` | class | index status DTO for curators |
| `application/use_cases/reindex_assistant.py` | `ReportSparseParameterChangesUseCase` | class | startup BM25 drift warning |
| `cli/worker.py` | `run_once` / `run_reindex_once` / `main` | function | polling loop: requeue+ingest, else reindex; SIGTERM-aware |
| `cli/check_consistency.py` | `main` / `report_events` | function | read-only PG vs Qdrant point-count check |
| `cli/purge_audit.py` | `main` | function | audit retention purge (runs migrations first) |
| `domain/chunking.py` | `DocumentBlock`, `ExtractedDocument`, `DocumentChunk` | dataclass | validated structural units |
| `infrastructure/chunking/sentences.py` | `split_sentences` | function | regex sentence splitter with PT abbreviations |
| `infrastructure/chunking/structural_chunker.py` | `StructuralDocumentChunker` | class | section-aware token-bounded packing with overlap |
| `infrastructure/documents/extractor.py` | `SupportedDocumentExtractor` | class | port adapter delegating to structured extraction |
| `infrastructure/documents/ocr.py` | `TesseractPdfOcr` | class | per-page pdftoppm + tesseract via subprocess |
| `infrastructure/documents/structured_extraction.py` | `extract_supported_document` | function | blocks from md/txt/pdf/docx/doc |
| `infrastructure/documents/text_extraction.py` | `resolve_document_type` | function | suffix/content-type -> supported type |
| `infrastructure/documents/text_extraction.py` | `extract_supported_text` | function | legacy flat-text extraction (no callers in src) |
| `infrastructure/storage/local_file_storage.py` | `LocalDocumentFileStorage` | class | originals under base_dir/<assistant>/<doc_id><ext> |

## Conventions observed
- **Naming**: snake_case functions, PascalCase classes, `_private` helpers; Portuguese docstrings, English log/error strings.
- **Error handling**: exceptions; class of exception drives retry policy (`ValueError`/`DomainValidationError`/`FileNotFoundError` = definitive, everything else = retry). Broad `except Exception` at worker loop and use-case boundaries.
- **Logging**: stdlib `logging` with dotted event names + `extra` dict (structured).
- **Async style**: fully synchronous; single-threaded polling worker; blocking subprocess calls.
- **Type hints**: fully typed; frozen slotted dataclasses for domain/value objects.

## Internal duplication
- PDF reading twice: `text_extraction.py:90` (`_extract_pdf_text`) vs `structured_extraction.py:231` (`_read_pdf_pages`); only the latter maps `PyPdfError` to `ValueError`.
- DOCX reading twice: `text_extraction.py:102` vs `structured_extraction.py:280`.
- `extract_supported_text` (`text_extraction.py:24`) is only re-exported from `infrastructure/documents/__init__.py`; dead path.
- "unsupported file format..." message literal in 3 places: `ingest_document.py:106`, `text_extraction.py:32`, `structured_extraction.py:49`.
- `_run_antiword` / `_run_catdoc` (`text_extraction.py:136`, `:150`) are identical except the binary name.
- `_utc_now` duplicated: `process_ingestion.py:53`, `reindex_assistant.py:46`.
- Qdrant gateway construction from env duplicated: `worker.py:150`, `check_consistency.py:107`.

## Cross-segment hints
- **data segment**: claims use `FOR UPDATE SKIP LOCKED` (`infrastructure/database/repositories.py:308`, `:436`, grep-only) — good, but `IngestionJobQueue.complete/retry/fail` and `ReindexJobRepository.save` need an ownership/fencing check (`WHERE status='reserved' AND attempts=:n`) to make the findings below safe. Verify there.
- **data segment**: confirm a DB unique constraint on `(assistant_id, content_hash)`; `find_by_hash` (`ingest_document.py:112`) is check-then-act under concurrent uploads.
- **domain segment**: confirm `ReindexInProgressError` / `IndexOutdatedError` are not subclasses of `DomainValidationError`/`ValueError`; if `ReindexInProgressError` is, the D8 race path (`process_ingestion.py:294`) fails documents definitively instead of retrying.
- **api segment**: size limit is checked after the whole upload is in memory (`ingest_document.py:89` receives `bytes`); enforce streaming limit / `Content-Length` at the route. Also confirm `IngestDocumentInput.document_id` / `new_document_id` (`ingest_document.py:201`, `:277`) are never client-supplied (see storage finding).
- **vector-store segment**: `DocumentIndexer.build_chunks` sends all chunk texts in one `embed_documents` call and one `upsert_chunks` (`document_indexing.py:85`, `process_ingestion.py:259`); batching must live in the gateways. Point id is `"<uuid>:<n>"` (`document_indexing.py:95`) — Qdrant needs UUID/int ids, so the gateway must hash deterministically.
- **ops/infra**: `purge_audit` and `check_consistency` have no in-code schedule; cron lives in platform config (not visible). `purge_audit.py:39` runs migrations from a maintenance CLI — can race API startup migrations.
- **notifications/observability**: terminal failures only go to log + audit (`process_ingestion.py:114-129`); no metric/alert counter for failed jobs, abandoned reindexes, or queue depth.

## Specialist findings

### Job inventory
| Job | Queue | File:Line | Idempotent? | Retries | Backoff | Notes |
|-----|-------|-----------|-------------|---------|---------|-------|
| ingest / replace (`ProcessNextIngestionJobUseCase`) | `ingestion_jobs` (PG, SKIP LOCKED) | process_ingestion.py:222 | mostly (deterministic ids + delete-before-upsert); not under concurrent owners | 3 (`max_attempts`) | fixed 30s, 120s, no jitter | no lease renewal; 600s fixed timeout |
| reprocess (`IngestionJobKind.REPROCESS`) | `ingestion_jobs` | ingest_document.py:404 | same as ingest | 3 | same | manual re-enqueue only |
| requeue expired (`RequeueExpiredIngestionJobsUseCase`) | in-loop sweep | process_ingestion.py:399 | yes | n/a | n/a | runs every iteration; counts timeout as attempt |
| reindex (`ProcessNextReindexJobUseCase` -> `RunReindexUseCase`) | `reindex_jobs` (PG, SKIP LOCKED, lease) | reindex_assistant.py:328 | restart-from-zero; unsafe with stale owner | 3 (lease expiries) | none (re-claim on lease expiry) | lease renewed per document only |
| check_consistency | CLI, external schedule | check_consistency.py:99 | yes (read-only) | none | — | reports, does not repair |
| purge_audit | CLI, external schedule | purge_audit.py:32 | yes (cutoff delete) | none | — | runs migrations |

### Locking / duplicate processing
- **HIGH** `process_ingestion.py:399-418` + `ingestion.py:50`: ingestion jobs have a fixed 600s timeout and **no heartbeat/lease renewal**. OCR alone allows 2x180s subprocesses per page (`ocr.py:36`, `:63-64`) and `.doc` conversion has no timeout. With >1 worker, another worker's sweep marks the still-running job expired, schedules a retry (30s later reserved by a second worker), and on the last attempt calls `_discard_partial_chunks` (`process_ingestion.py:111`) while the first worker is still writing. Outcomes: two owners running `delete_by_document` -> `upsert` -> `set_document_active` (`:258-263`) interleaved, a document `INDEXED` in PG with zero/inactive points, or a `FAILED` doc later overwritten to `INDEXED` by the stale owner. Fix: renew lease per page/batch (as reindex does) and fence `complete/retry/fail` on attempt number.
- **HIGH** `reindex_assistant.py:229-235`: lease renewed only after each document; a single large/OCR document > `lease_seconds` (600) lets another worker re-claim. The new owner runs `_discard(target)` (`:208`) deleting the collection the old owner is writing to; the old owner's `except` path also `_discard(target)` (`:191-192`) and can delete the new owner's collection, or both reach `_swap_alias`. `_reindex_job_repository.save(progress)` (`:235`) has no ownership check, so the stale owner overwrites progress/lease. Fix: fencing token (attempts) in `save`, check ownership before discard/swap, renew lease inside `_reindex_document`.

### Idempotency / PG-Qdrant consistency
- **MED** `process_ingestion.py:263-275`: activation, deletion of previous version, and `queue.complete` are three non-atomic steps. Failure after `:263` (e.g. PG error in `complete`) goes to `handle()` -> retry: the new version's chunks stay **active and searchable while the doc is PENDING**, alongside the previous version's chunks (duplicate answers). If retries then exhaust, `_discard_partial_chunks` removes the new chunks; if `:265` had already run, the previous version is `INDEXED` in PG with no points.
- **MED** `reindex_assistant.py:178-185`: alias swap + old collection delete (`:273-275`) happen before PG document updates (`:180-181`). Crash in between leaves PG docs on old `embedding_model/pipeline_version`; the re-claimed job hits "target collection is already in use" (`:175-176`) and fails; `is_index_outdated` then blocks all uploads until a manual new reindex. Exception after `swapped=True` also marks job FAILED although the swap succeeded.
- **LOW** `ingest_document.py:149-169`: `storage.save` happens before `documents.save` and outside the try; a PG failure leaves an orphan file. Compensation in `:176-180` only covers groups/enqueue.
- **OK** deterministic chunk ids (`document_indexing.py:95`) + delete-before-upsert (`process_ingestion.py:258`) make single-owner retries idempotent, including shrinking chunk counts.

### Retry config / poison jobs
- **MED** `process_ingestion.py:152-160`: classification by exception type misroutes common errors. Corrupt DOCX raises `zipfile.BadZipFile`/`KeyError`/`PackageNotFoundError` (`structured_extraction.py:296`), `.doc` without tools raises `RuntimeError` (`text_extraction.py:130`), pypdf non-`PyPdfError` errors (`structured_extraction.py:243-248`), OCR `subprocess.TimeoutExpired` (`ocr.py:95`) — all retried 3x then reported as "serviço interno indisponível". Conversely `ValueError("unexpected vector count")` from the provider (`document_indexing.py:88`) and pydantic `ValidationError` (a `ValueError`) are failed definitively without retry.
- **LOW** `process_ingestion.py:402-405`: expired jobs whose document is gone/not in progress are `continue`d without closing the job; they are re-listed on every poll forever.
- **LOW** `ingestion.py:64`: fixed delays, no jitter; fine at 3 attempts. `ReindexInProgressError` retries consume attempts during a long reindex (`process_ingestion.py:294`) — race-only path per D8.
- Reindex retries are re-claims only on lease expiry; a reindex that fails with an exception is FAILED immediately (`reindex_assistant.py:186-193`) with no automatic retry — acceptable, user restarts.

### Dead-letter handling
- **MED** No DLQ; terminal state is `job.fail` + `document.FAILED` + audit event (`process_ingestion.py:110-129`). Inspection is manual (curator UI / reprocess). No failure-rate metric, no queue-depth/oldest-job metric, no alert for `reindex.abandoned` (`reindex_assistant.py:352`).

### Sync calls without timeouts / long-running work
- **HIGH** `text_extraction.py:139`, `:153`, `:168`: `antiword`, `catdoc`, `soffice` run with **no `timeout`**. A hung LibreOffice (common with malformed input or a locked shared profile) blocks the single-threaded worker forever; no SIGTERM path reaches it, and the job expires and re-hangs the next worker (poison pill that takes down the whole pool).
- **MED** pypdf / python-docx parse in-process with no time or memory bound (`structured_extraction.py:244-245`, `:296`); malicious PDFs (deep recursion, huge object streams) and DOCX zip bombs can hang or OOM the worker. Run extraction in a subprocess with `timeout` + `RLIMIT_AS`, or at least a page-count cap.
- Embedding/Qdrant call timeouts live in gateways (not in this segment) — verify.

### Memory / large files
- **MED** `structured_extraction.py:252-255` + `ocr.py:61-62`: for each image-only page the **whole PDF is rewritten to a temp file** and re-parsed by `pdftoppm`; N scanned pages = N full writes + N full parses. No max page count; 300 DPI on large page sizes yields very large PNGs. Render once (`pdftoppm` whole range into one temp dir) and cap pages.
- **MED** `structural_chunker.py:209-210`, `:150-152`: `_fits` re-tokenizes the growing chunk body on every unit/row (quadratic per chunk). Large tables/many short sentences burn CPU, pushing jobs past the 600s timeout above.
- **LOW** Whole file in memory at every stage (`local_file_storage.py:42`, all chunks + vectors in one list `document_indexing.py:93`); bounded by `max_file_bytes` only at intake.

### Graceful shutdown / crash recovery
- **LOW** `worker.py:163-184`: SIGTERM sets an event; the in-flight job finishes. Container stop grace (default 10s) is far below job runtime, so SIGKILL is the normal path; recovery depends on the 600s timeout and burns an attempt. Document `stop_grace_period` or check `stop` between pages/batches and release the job.
- **OK** crash recovery for stuck "processing": `RequeueExpiredIngestionJobsUseCase` (`process_ingestion.py:399`) and lease re-claim for reindex.

### Concurrency model
- Single-threaded process, horizontal scaling by replicas; adapters are per-process and stateless (`worker.py:67-75`). No shared mutable state across processes except PG/Qdrant/filesystem.
- **LOW** `worker.py:173-184`: reindex runs only when the ingestion queue is empty; steady uploads to other assistants starve reindex jobs.
- **LOW** `text_extraction.py:168`: concurrent `soffice` instances in the same container share the default user profile and fail/lock; pass `-env:UserInstallation=file://<tmp>`.

### Backpressure
- **LOW** One job per upload, no per-assistant cap on pending jobs or queue-depth guard; bulk uploads queue unbounded. No producer loops enqueue per row in this segment.

### Scheduling
- `check_consistency` and `purge_audit` are declared only as CLIs; scheduling is external (not in code). No drift risk visible from code, but nothing ensures they run.

### File storage safety
- **OK** path traversal: key built from sanitized ids + regex-validated suffix (`local_file_storage.py:30-32`); `_resolve` enforces `is_relative_to(base_dir)` (`:48-54`). User filename never reaches the path.
- **MED** `local_file_storage.py:35` overwrites silently. If `document_id` can be caller-influenced (`ingest_document.py:243`, `:331`), an upload with an existing id overwrites that document's original before `documents.save` fails on PK. `_safe` is also non-injective (`a.b` and `a-b` map to the same file, `:58`). Use `open(path, "xb")` or check existence.
- **LOW** `local_file_storage.py:35`: non-atomic write (no temp + `os.replace`, no fsync); a crash mid-write leaves a truncated original that the worker will later fail on as "unreadable".
- **LOW** type validation is extension + declared content-type only (`text_extraction.py:47-80`); no magic-byte sniffing. Parsers are the de-facto validator (see hang/OOM findings).
- **LOW** `.txt`/`.md` must be UTF-8 (`text_extraction.py:83-87`); cp1252/latin-1 corporate files fail definitively.

### Chunking edge cases
- **LOW** `structural_chunker.py:186-196` + `:177`: oversize words are halved and re-joined with spaces, injecting spaces into URLs/IDs/base64.
- **LOW** `structural_chunker.py:270`: chunk `page` is the first unit's page; chunks spanning pages lose later pages for citations.
- **LOW** `structured_extraction.py:28`, `:221-228`: PDF heading heuristic accepts lines like "2024 Relatório anual" or table rows "10 Funcionários ativos" as headings, corrupting `section_path`.
- **LOW** `structured_extraction.py:136-155`: unclosed fence turns the rest of a Markdown file into one CODE block; setext headings (`---` underline) are swallowed by `_RULE`.

## Concerns / smells
1. No lease renewal / fencing for ingestion jobs and per-document-only renewal for reindex: multi-worker deployments double-process and can delete each other's Qdrant data (`process_ingestion.py:399`, `reindex_assistant.py:208`, `:229-235`).
2. Timeout-less subprocesses for `.doc` (`text_extraction.py:139/153/168`) and unbounded in-process parsers: one bad file hangs workers serially (poison pill).
3. Exception-type retry classification misroutes corrupt-file and provider errors (`process_ingestion.py:152-160`).
4. Non-atomic activation/complete and swap/PG-update sequences leave PG and Qdrant inconsistent after partial failure (`process_ingestion.py:263-275`, `reindex_assistant.py:178-185`).
5. No DLQ-style visibility: no metrics or alerts for failed/abandoned jobs or queue depth.

## Refactor suggestions
1. `process_ingestion.py` + `IngestionJobQueue`: add `renew(job, until)` called from `DocumentIndexer` progress hooks (per page/batch) and make `complete/retry/fail` conditional on `(id, attempts, status='reserved')`; abort work if the update affects 0 rows.
2. `reindex_assistant.py:244`: renew lease inside `_reindex_document` (per OCR page / embed batch) and make `ReindexJobRepository.save` fence on `attempts`; skip `_discard`/`_swap_alias` if ownership is lost.
3. `text_extraction.py:136-190` + `ocr.py`: one shared `_run_tool(cmd, timeout)` helper with timeout, isolated LibreOffice profile, and map `TimeoutExpired` to a dedicated retryable error; run pypdf/docx parsing under a page cap and subprocess with `RLIMIT_AS`.
4. `process_ingestion.py:152`: replace type-based classification with explicit `UnreadableDocumentError` / `TransientServiceError` raised by extractors and gateways; wrap pypdf/docx/zip errors as unreadable.
5. Delete `extract_supported_text`, `_extract_pdf_text`, `_extract_docx_text` (`text_extraction.py:24-113`) and keep only `structured_extraction.py`; move `_extract_doc_text` there. Make `LocalDocumentFileStorage.save` (`local_file_storage.py:35`) atomic and non-overwriting (temp file + `os.replace`, fail if exists).
