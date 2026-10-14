# Segment: devops-infra

**Reviewed by:** devops-config-reviewer

## Files reviewed
- `.dockerignore`
- `.env.example`
- `.github/workflows/ci.yml`
- `backend/requirements.txt`
- `compose.yaml`
- `frontend/package.json`
- `infra/docker/README.md`
- `infra/docker/backend.Dockerfile`
- `infra/docker/backup.Dockerfile`
- `infra/docker/frontend.Dockerfile`
- `scripts/backup-common.sh`
- `scripts/backup-loop.sh`
- `scripts/backup.sh`
- `scripts/eval.ps1`
- `scripts/eval.sh`
- `scripts/quality-gate.sh`
- `scripts/restore.sh`

## Integrations
- docker (Compose v2, 3 Dockerfiles, named volumes, profiles `observabilidade` and `backup`)
- ci (GitHub Actions, single workflow `ci.yml`)
- postgresql (pg_dump/pg_restore in backup sidecar)
- qdrant (REST snapshots in backup/restore)
- keycloak (start-dev, realm import, DB created by `keycloak-db-init`)
- prometheus / grafana / jaeger (profile `observabilidade`)

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `compose.yaml:2` | `backend` | service | API, built from backend.Dockerfile, healthcheck on /health |
| `compose.yaml:39` | `worker` | service | Same image as backend, runs `src.cli.worker`, no healthcheck |
| `compose.yaml:59` | `frontend` | service | Nginx + Angular build, healthcheck via wget |
| `compose.yaml:81` | `postgres` | service | postgres:16-alpine, volume `postgres_data`, published 5432 |
| `compose.yaml:101` | `keycloak-db-init` | service | One-shot: creates `keycloak` database if missing |
| `compose.yaml:120` | `keycloak` | service | quay.io Keycloak 26.0 in `start-dev`, realm import |
| `compose.yaml:163` | `qdrant` | service | qdrant v1.11.3, API key, TCP-only healthcheck |
| `compose.yaml:181` | `jaeger` | service | In-memory tracing, profile observabilidade |
| `compose.yaml:191` | `prometheus` | service | 7d retention, profile observabilidade |
| `compose.yaml:206` | `grafana` | service | Provisioned dashboards, profile observabilidade |
| `compose.yaml:226` | `backup` | service | Sidecar looping backup.sh, profile backup |
| `infra/docker/backend.Dockerfile` | single stage | image | python:3.12-slim + OCR + CPU torch + requirements |
| `infra/docker/frontend.Dockerfile` | `build` / nginx | image | node:22-alpine build, nginx:1.27-alpine runtime |
| `infra/docker/backup.Dockerfile` | single stage | image | postgres:16-alpine + curl/jq/tar + backup scripts |
| `.github/workflows/ci.yml:19` | `backend` | ci job | ruff (F,E9), compileall, unittest |
| `.github/workflows/ci.yml:51` | `frontend` | ci job | npm ci, vitest, ng build |
| `.github/workflows/ci.yml:69` | `infra` | ci job | realm grep checks, `compose config -q`, `sh -n` on backup scripts |
| `scripts/backup-common.sh:17` | `log` | function | Timestamped line to stdout |
| `scripts/backup-common.sh:21` | `fail` | function | Log error and exit 1 |
| `scripts/backup-common.sh:27` | `qdrant` | function | curl wrapper with api-key header |
| `scripts/backup-common.sh:34` | `database_exists` | function | psql lookup in pg_database |
| `scripts/backup-common.sh:39` | `write_counts` | function | Row/point/file counts used to verify restore |
| `scripts/backup.sh` | main | script | pg_dump x2, Qdrant snapshots, docs tar, checksums, retention |
| `scripts/backup-loop.sh` | main | script | Runs backup.sh every N seconds, retry 1h on failure |
| `scripts/restore.sh:30` | `restore_database` | function | Create-if-missing then `pg_restore --clean` |
| `scripts/restore.sh` | main | script | Verify checksums, restore PG, Qdrant, aliases, docs, compare counts |
| `scripts/eval.sh` / `scripts/eval.ps1` | main | script | `compose run` the RAG evaluation CLI (bash and PowerShell twins) |
| `scripts/quality-gate.sh` | main | script | Unit tests + retrieval eval (+ fidelity eval with flag) |

## Conventions observed
- **Naming**: UPPER_SNAKE env vars with mixed prefixes (`NEXUS_`, `KEYCLOAK_`, `OIDC_`, `BACKUP_`, `QDRANT_`); kebab-case compose services; snake_case shell functions; Dockerfiles named `<service>.Dockerfile`.
- **Error handling**: backup/restore are POSIX `sh` with `set -eu` and no pipefail; eval/quality-gate are bash with `set -euo pipefail`; backup-loop uses `set -u` only (deliberate); eval.ps1 uses `$ErrorActionPreference=Stop` plus `exit $LASTEXITCODE`.
- **Logging**: plain `printf` ISO-8601 UTC lines from `log()`; no structured output; no log rotation options in compose.
- **Async style**: n/a (infra). Startup ordering via `depends_on` with `service_healthy` for postgres/qdrant/backend, `service_started` for keycloak.
- **Type hints**: n/a. Comments are pt-BR ASCII without accents, annotated with SPEC/ADR ids.
- **Images**: all pinned to a tag (none to a digest); none use `:latest`.

## Internal duplication
- `scripts/eval.sh` and `scripts/eval.ps1` duplicate the same argument parsing and `docker compose run` invocation (full copy, no shared source).
- Default values for the same setting are repeated in compose and `.env.example` (see Env var registry): Qdrant key, Postgres creds, Keycloak admin, Grafana admin, ports.
- `torch==2.5.1` is pinned separately in `infra/docker/backend.Dockerfile:20` and `.github/workflows/ci.yml:38`.
- Tail of the pre-flight "OCR packages" list is duplicated in `backend.Dockerfile:12` and `ci.yml:34`.

## Cross-segment hints
- Verify the backend refuses default secrets (`NEXUS_SECRETS_KEY=change-me-in-local-env`, `nexus` DB password, `nexus-local` Qdrant key) when `APP_ENV` is not `local`; nothing in this segment enforces it (api-http / auth reviewers).
- `/metrics` exposure: `compose.yaml:11-12` publishes the backend port on all host interfaces, so the Nginx-only protection noted by another reviewer is bypassable at `host:8000/metrics` (api-http / auth).
- `CORS_ALLOWED_ORIGINS` (`.env.example:77`) must be kept manually in sync with `NEXUS_FRONTEND_URL` (`.env.example:68`): candidate for deriving one from the other in the config module.
- `API_HOST` / `API_PORT` (`.env.example:2-3`) are not used by the Dockerfile CMD (`backend.Dockerfile:32` hardcodes 0.0.0.0:8000); check whether the app config reads them.
- Table list in `backup-common.sh:15` is hardcoded; the database/migrations reviewer should confirm it covers all tables (e.g. ingestion job tables are not counted).
- `LLM_API_KEY` is absent from `.env.example` while `LLM_PROVIDER=openai`; confirm how the key is supplied (likely encrypted in DB via `NEXUS_SECRETS_KEY`).
- `frontend/nginx/default.conf.template` and `infra/keycloak/nexus-realm.json` are outside this segment; healthcheck path `/health` and the realm placeholders depend on them.
- Frontend `ng build` output path assumed to be `/app/dist` (`frontend.Dockerfile:16`); confirm against `angular.json`.

## Specialist findings

### Secrets and defaults (verification of the other reviewer's notes)
- **High** `compose.yaml:141`, `.env.example:74`: `NEXUS_BACKEND_CLIENT_SECRET` placeholder in the realm resolves to the public default `nexus-backend-dev-secret` (`${KEYCLOAK_BACKEND_CLIENT_SECRET:-...}`). No `:?` required-variable syntax, so an unset variable silently boots with a known secret. The comment at `.env.example:71` ("Troque fora do ambiente local") is not enforced anywhere.
- **High** `compose.yaml:7,45,65,84,104,232`: `.env.example` is loaded as a required `env_file` for every service and `.env` is only an optional override. The example file therefore acts as the production default set; there is no `compose.prod.yaml` or fail-fast for unchanged defaults.
- **High** Weak defaults, all published to the host: Postgres `nexus/nexus` (`.env.example:10-11`), Keycloak admin `admin/admin` (`.env.example:63-64`, `compose.yaml:128-129`), Grafana `admin/admin` (`compose.yaml:210-211`), Qdrant key `nexus-local` (`compose.yaml:166`, `.env.example:15`), `NEXUS_SECRETS_KEY=change-me-in-local-env` (`.env.example:51`, the key that encrypts stored secrets).
- **Med** `compose.yaml:64-68`, `83-87`, `104-107`: whole env file (DB password, secrets key, Keycloak secret) is injected into `frontend`, `postgres`, `keycloak-db-init`; only the Nginx login addresses are needed by the frontend. Use per-service `environment:`.
- **Med** `.env.example:9-12`: Postgres credentials appear in four places (`POSTGRES_USER/PASSWORD/DB` and embedded in `DATABASE_URL`); changing the password in one place breaks the other silently.
- **Low** No secrets echoed in logs or passed as build args; `backup-common.sh:26` correctly keeps the Qdrant key out of the log. CI uses no secrets (`ci.yml` header comment) and `permissions: contents: read` (`ci.yml:11`).

### Published ports and exposure
- **High** `compose.yaml:11,69,88,142,167,186,197,213`: every service publishes on all interfaces (no `127.0.0.1:` prefix): backend 8000, frontend 4200, Postgres 5432, Keycloak 8080, Qdrant 6333, Jaeger 16686, Prometheus 9090, Grafana 3000. Postgres (superuser `nexus`), Qdrant, Prometheus, Jaeger have no network-layer gating; only frontend (and Keycloak for login) need host access.
- **High** `compose.yaml:11-12`: backend published directly, so `/metrics` and any proxy-only control are reachable without Nginx.
- **High** `compose.yaml:122`: Keycloak runs `start-dev` (HTTP, dev caches, no hostname strictness) with `KC_HTTP_ENABLED=true`; `KC_HOSTNAME` default is `http://localhost:8080`. Not a production profile.

### Image hygiene
- **Med** `infra/docker/backend.Dockerfile`, `backup.Dockerfile`, `frontend.Dockerfile`: no `USER` in any final stage; backend, backup and nginx all run as root. Backup writes root-owned files onto the host bind mount (`compose.yaml:237`).
- **Med** All base images use movable tags without digests (`python:3.12-slim`, `node:22-alpine`, `nginx:1.27-alpine`, `postgres:16-alpine`); `apk add curl jq tar` (`backup.Dockerfile:5`) unpinned.
- **Med** Image versions date from late 2024 (Keycloak 26.0, Qdrant v1.11.3, Grafana 11.3.0, Prometheus 2.55.1, Jaeger 1.62.0); no update automation or image scan in CI.
- **Med** `backend.Dockerfile:20-24`: `torch` is installed outside `requirements.txt` and transitive deps are unpinned with no lockfile or hashes; rebuilds are not reproducible.
- **Med** `frontend.Dockerfile:5-6`: `npm install` with optional lockfile glob (`package-lock.json*`) instead of `npm ci`; CI uses `npm ci` (`ci.yml:63`), so CI and image can resolve different trees.
- **Med** `.dockerignore:1-9`: build context is `.` for backend, frontend and backup, but `backups/`, `.env`, `.venv`, `frontend/.angular`, `docs/` are not excluded; the `./backups` bind folder (`.env.example:107`) would be streamed to the daemon on every build and `COPY frontend .` (`frontend.Dockerfile:8`) copies any local `frontend/.env`/`.angular` cache into the build stage.
- **Low** `backend.Dockerfile`: single stage is acceptable (no compiler toolchain); `--no-install-recommends` and apt list cleanup are correct; pip uses `--no-cache-dir`. No `HEALTHCHECK` in images (compose provides them).
- **Low** `HF_HUB_OFFLINE=0` (`.env.example:35`): models are downloaded at runtime from the Hub into `backend_cache` (`compose.yaml:14,50`), unpinned by revision; first start of backend and worker can race on the shared cache volume.
- **Low** `infra/docker/README.md:3-29`: stale; says Docker env is "planned" and lists worker, volumes, observability as "not created" though all exist; omits `backup.Dockerfile`, lists a non-existent `scripts/`.

### Healthchecks, readiness, ordering
- **Med** `compose.yaml:39-57`: `worker` has no healthcheck and runs ML models; a hung worker is not detected (only `restart: unless-stopped`, line 54).
- **Med** Restart policy is set only on `worker` and `backup` (`compose.yaml:54,239`); `backend`, `frontend`, `postgres`, `qdrant`, `keycloak` have none, so a crash leaves the stack down.
- **Low** `compose.yaml:172`: Qdrant healthcheck is a bare TCP connect; it passes before the API is ready.
- **Low** `compose.yaml:219-221`: grafana `depends_on` prometheus/jaeger with no condition, and those have no healthchecks; backup service and jaeger/prometheus/grafana lack healthchecks.
- **Low** `compose.yaml:35`: backend only waits `service_started` for Keycloak (documented, acceptable).
- **Low** `compose.yaml:112-114`: db-init is check-then-create without error handling for a concurrent create; fine for single-run use.

### Resource limits and logging
- **Med** No `mem_limit`/`deploy.resources` anywhere. Backend and worker each load the embedding and reranker models (`.env.example:17,37`) from the same image, doubling RAM; Keycloak (JVM) and Qdrant are unbounded.
- **Low** No `logging:` options; the default json-file driver grows without rotation.
- **Low** Observability is opt-in (`profiles`, `compose.yaml:183,193,208`) with Prometheus + Jaeger + Grafana; OTLP endpoint empty by default (`.env.example:99`), so tracing is off unless the user edits `.env`.

### Volumes and persistence
- **Low** Postgres, Qdrant, uploads (`documents_data`), model cache, Prometheus and Grafana all use named volumes (`compose.yaml:246-252`); persistence is correct.
- **Med** Backups default to `./backups` on the same host and disk as the data (`compose.yaml:237`, `.env.example:107`); no off-host copy, no encryption. Dumps contain document content and the Keycloak DB (credential hashes) in plaintext.
- **Med** `NEXUS_SECRETS_KEY` is not part of the backup (`backup.sh` manifest lines 53-57); encrypted secrets in the restored DB are unrecoverable if the key is lost. The runbook is not in this segment.

### Backup and restore correctness
- **High** `scripts/backup.sh:28-48`: Postgres dump, Qdrant snapshots and the documents tar are taken sequentially with the worker/API still running (the restore doc stops services, backup does not). The three stores can disagree (document row without vectors, orphan files).
- **Med** `scripts/backup.sh:52`: `counts.txt` is written after the dumps, from live data; any write between `pg_dump` and `write_counts` makes the later `restore.sh` count comparison (`restore.sh:77`) fail spuriously, and the check cannot tell which side is wrong.
- **High** Restore is never exercised: CI only runs `sh -n` on the four scripts (`ci.yml:84-88`); no job restores a dump into a scratch Postgres/Qdrant. `eval.sh`, `quality-gate.sh` are not even syntax-checked (no shellcheck anywhere).
- **Med** `scripts/backup.sh:38,58` and `backup-common.sh:42,45`: no `pipefail` in POSIX sh; failures inside `$(... | jq ...)` or `find | sort | xargs sha256sum` are masked. If `GET /collections` fails after the aliases call succeeded, the loop is empty and the backup still reports success with no Qdrant data.
- **Med** `scripts/backup-loop.sh:9-16`: no failure alerting beyond stderr, no healthcheck on the `backup` service, no `trap` for SIGTERM (PID 1 `sh` sleeping ignores it, so `docker stop` waits then SIGKILLs, possibly mid-backup, leaving `.partial`, which the next run cleans).
- **Low** `scripts/backup.sh:65-70`: retention is age-only (`-mmin`); there is no minimum number of kept backups, and `-name '20*Z'` is a hard-coded pattern. Disk space is not checked before writing.
- **Low** `scripts/backup-common.sh:15`: hardcoded table list; new tables are silently excluded from the restore verification.
- **Low** `scripts/restore.sh:30-37`: `pg_restore --clean` while other clients are connected fails with `--exit-on-error` midway; the script relies on the operator stopping services (documented in the header, not checked).
- **Positive** Atomic `.partial` rename (`backup.sh:60`), SHA256SUMS verified before restore (`restore.sh:27`), snapshot deleted from Qdrant after download (`backup.sh:42`), `--yes` guard on restore, counts compared after restore.

### Dependency pinning
- **Med** `backend/requirements.txt:1-12`: direct dependencies exact-pinned (good) but no lockfile, hashes or constraints for transitive packages (starlette, pydantic, numpy, transformers, huggingface-hub); no dev/test requirements file (ruff installed ad hoc at `ci.yml:42`).
- **Med** `backend/requirements.txt:6` vs `compose.yaml:164`: `qdrant-client==1.19.1` against server `qdrant/qdrant:v1.11.3`; client/server minor gap far above the supported one-minor window, risk of API incompatibility and client warnings.
- **Med** `backend/requirements.txt`: stack is old relative to today's date (fastapi 0.115.12, uvicorn 0.34.2, sentence-transformers 3.3.1, alembic 1.14.0) and nothing audits it.
- **Med** `frontend/package.json:12-39`: all caret ranges (`^19.2.0` etc.); reproducibility depends entirely on `package-lock.json` (not in this segment's file list; existence not verified here). No `engines` field although node 22 is assumed (`frontend.Dockerfile:1`, `ci.yml:61`).
- **Low** `frontend/package.json:5-10`: no `lint` script; `@types/node ^22` and `vitest ^4.1.5` float within major.

### CI workflow inventory
| Workflow | Trigger | Jobs | Secrets |
|----------|---------|------|---------|
| `.github/workflows/ci.yml:4` (`ci`) | push to `main`, `feat/**` (line 8); every `pull_request` (line 9) | `backend` (19), `frontend` (51), `infra` (69) | none (default read-only GITHUB_TOKEN) |

- **Med** No job builds the three Dockerfiles; `docker compose config -q` (`ci.yml:82-83`) only validates syntax. A broken Dockerfile or `npm install` vs `npm ci` divergence reaches users first.
- **Med** No dependency or image audit (`pip-audit`, `npm audit`, Trivy), no secret scanning, no Dependabot/Renovate config in this segment.
- **Med** Lint is minimal: `ruff check --select F,E9` only (`ci.yml:43`); no formatter, no type check (`.dockerignore:4,9` mention mypy caches, so it is used locally), no frontend lint.
- **Med** Integration tests are not run: the backend job has no Postgres/Qdrant services; `DATABASE_URL` at `ci.yml:47` points at a non-existent localhost database.
- **Low** Actions pinned by tag (`checkout@v4`, `setup-python@v5`, `setup-node@v4`), not SHA; no `timeout-minutes` on jobs (torch install is heavy).
- **Low** `ci.yml:14-16`: `cancel-in-progress: true` also cancels in-flight runs on `main` pushes.
- **Low** `ci.yml:76-79`: realm guards are string-presence greps; they would pass with any value for the secret.
- **Low** No CD workflow exists; deploy-target and required-review checks are not applicable.
- **Positive** `ubuntu-24.04` pinned, `permissions: contents: read`, pip and npm caches keyed on dependency files, torch CPU index matches the image.

### Script robustness
- **Med** `scripts/quality-gate.sh:28-30` and `scripts/eval.sh:19-28`: `docker compose run` does not rebuild; `src` is baked into the image (`backend.Dockerfile:27`), so the gate and eval test the last built image, not the working tree. Only `backend/tests` is bind-mounted. Add `--build` or a preceding `docker compose build backend`.
- **Low** `scripts/eval.sh:19` uses `--no-deps`; Postgres and Qdrant must already be running, which is undocumented. It seeds `docs/` into the same Postgres/Qdrant as dev data (`--seed-dir`), so evaluation can pollute a working environment.
- **Low** `scripts/quality-gate.sh:20-25`: any unrecognised argument (including `--help`, `--fidelity`) is taken as the dataset name.
- **Low** `scripts/eval.ps1` has no `Set-StrictMode`; no PowerShell twin for `quality-gate.sh` or backup scripts (platform parity gap).
- **Low** `scripts/backup-common.sh` has no shebang or `set`; it relies on being sourced after `set -eu`.
- **Positive** `eval.sh`/`quality-gate.sh` use `set -euo pipefail` and quote arguments; `backup.sh` validates `BACKUP_RETENTION_DAYS` as an integer.

### Env var registry
| Var name | Used in (file:line) | Has default? | Notes |
|----------|---------------------|--------------|-------|
| DATABASE_URL | `.env.example:12`, `ci.yml:47` | yes | embeds POSTGRES_USER/PASSWORD/DB; duplicated credentials; CI value differs (localhost) |
| POSTGRES_USER | `.env.example:10`, `compose.yaml:93,126`, `backup-common.sh:10` | yes (`nexus`) | compose default `nexus`; backup requires it (`:?`) |
| POSTGRES_PASSWORD | `.env.example:11`, `compose.yaml:127`, `backup-common.sh:11` | yes (`nexus`) | weak default, published port |
| POSTGRES_DB | `.env.example:9`, `compose.yaml:93`, `backup-common.sh:12` | yes (`nexus`) | — |
| BACKEND_PORT | `.env.example:4`, `compose.yaml:12` | yes (8000) | duplicates API_PORT intent |
| API_PORT / API_HOST | `.env.example:2-3` | yes | CMD hardcodes 0.0.0.0:8000 (`backend.Dockerfile:32`); possibly unused |
| API_BASE_URL | `.env.example:85` | yes | third spelling of the backend address (vs BACKEND_PORT, CORS) |
| QDRANT_URL | `.env.example:14` | yes | duplicated by BACKUP_QDRANT_URL |
| BACKUP_QDRANT_URL | `backup-common.sh:7` | yes (`http://qdrant:6333`) | not in `.env.example`; duplicates QDRANT_URL |
| QDRANT_API_KEY | `.env.example:15`, `compose.yaml:166`, `backup-common.sh:31` | inconsistent | defaults: `nexus-local` (compose, example), empty (backup) |
| KEYCLOAK_URL | `.env.example:57`, `compose.yaml:132` | yes | feeds KC_HOSTNAME; browser-facing issuer |
| KEYCLOAK_INTERNAL_URL | `.env.example:59` | yes | duplicate of KEYCLOAK_URL for backchannel |
| KEYCLOAK_ADMIN / _PASSWORD | `.env.example:63-64`, `compose.yaml:128-129` | yes (`admin/admin`) | renamed to KC_BOOTSTRAP_ADMIN_* |
| KEYCLOAK_BACKEND_CLIENT_SECRET | `.env.example:74`, `compose.yaml:141` | yes (`nexus-backend-dev-secret`) | renamed NEXUS_BACKEND_CLIENT_SECRET for the realm; two names, one value |
| NEXUS_FRONTEND_URL | `.env.example:68`, `compose.yaml:138` | yes | must also be in CORS_ALLOWED_ORIGINS |
| CORS_ALLOWED_ORIGINS | `.env.example:77` | yes | manual duplicate of NEXUS_FRONTEND_URL |
| NEXUS_SECRETS_KEY | `.env.example:51` | placeholder | `change-me-in-local-env`; not in backup |
| HF_HOME | `.env.example:34`, `backend.Dockerfile:16` | yes | set twice |
| HF_HUB_OFFLINE | `.env.example:35`, `ci.yml:48` | yes (0) | runtime model download in containers |
| DOCUMENTS_STORAGE_PATH | `.env.example:26`, `compose.yaml:15,51` | yes | mount target hardcoded separately in compose and Dockerfile:17 |
| BACKUP_PATH | `.env.example:107`, `compose.yaml:237` | yes (`./backups`) | host path; not the same as BACKUP_DIR |
| BACKUP_DIR | `backup-common.sh:4` | yes (`/backups`) | container path; undocumented |
| BACKUP_DOCUMENTS_DIR / BACKUP_PGHOST / BACKUP_KEYCLOAK_DB | `backup-common.sh:5,6,8` | yes | undocumented in `.env.example` |
| BACKUP_RETENTION_DAYS | `.env.example:108`, `backup.sh:15` | yes (7) | validated integer |
| BACKUP_INTERVAL_SECONDS | `.env.example:109`, `backup-loop.sh:6` | yes (86400) | — |
| GRAFANA_ADMIN_USER / _PASSWORD | `.env.example:104-105`, `compose.yaml:210-211` | yes (`admin/admin`) | weak default |
| GIT_COMMIT | `scripts/eval.sh:17`, `scripts/eval.ps1:14` | yes (`unknown`) | passed into the container |
| EVAL_REGRESSION_TOLERANCE | `.env.example:83`, `quality-gate.sh:9` (comment) | yes | read by the backend CLI, not by the script |
| OTEL_EXPORTER_OTLP_ENDPOINT | `.env.example:99`, `compose.yaml:180` (comment) | empty | tracing off by default |

## Concerns / smells
1. **High** Default credentials (`nexus`, `admin`, `nexus-local`, `nexus-backend-dev-secret`, `change-me-in-local-env`) ship as the required base env file and nothing fails fast when unchanged, combined with every service published on all host interfaces, including Postgres, Qdrant, Keycloak `start-dev`, Prometheus, and the backend itself (bypasses the Nginx `/metrics` protection).
2. **High** Backup is not cross-store consistent (Postgres, Qdrant and files dumped at different moments with writers running) and the restore path is untested in CI (syntax check only).
3. **Med** Images run as root, are unpinned by digest, and are about two years old; builds are not reproducible (no lockfile or hashes for Python, `npm install` in the image vs `npm ci` in CI).
4. **Med** CI does not build the images, run integration tests, lint beyond F/E9, audit dependencies, or scan secrets; `qdrant-client 1.19.1` vs server `v1.11.3` mismatch goes unchecked.
5. **Med** `quality-gate.sh` and `eval.sh` run against the last built image rather than the working tree, so a green gate can describe stale code.

## Refactor suggestions
1. `compose.yaml` (all `env_file` blocks, lines 6-9 etc.): replace the required `.env.example` load with a `.env`-required model or use `${VAR:?}` for secrets (`POSTGRES_PASSWORD`, `QDRANT_API_KEY`, `KEYCLOAK_*`, `NEXUS_SECRETS_KEY`) and scope `environment:` per service. Why: removes silent default secrets and least-privilege leakage.
2. `compose.yaml` ports (lines 11,69,88,142,167,186,197,213): bind to `127.0.0.1:` for postgres, qdrant, backend, keycloak, prometheus, jaeger, grafana and publish only the frontend. Why: closes direct DB/vector/metrics access and the `/metrics` bypass.
3. `scripts/backup.sh` + `.github/workflows/ci.yml`: quiesce writers (stop worker, or take Postgres first then Qdrant under a write pause), write `counts.txt` from the dump source, add `set -o pipefail`, and add a CI job that runs backup then restore against ephemeral Postgres/Qdrant service containers plus `shellcheck` over all scripts. Why: proves consistency and restore.
4. `infra/docker/*.Dockerfile`: add non-root `USER` (or `nginx-unprivileged`), pin base images by digest, switch frontend to `npm ci`, and add `pip-compile`/`uv` lock with hashes plus torch in the lock; align the Qdrant client and server versions. Why: security and reproducibility.
5. `.github/workflows/ci.yml` and `scripts/quality-gate.sh`: add a `docker compose build` job, `pip-audit`/`npm audit`, Trivy, Dependabot; add `--build` to `compose run` in quality-gate/eval. Why: catches broken images and stale-image gate results.
