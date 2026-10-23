# Segment: auth-access-control

**Reviewed by:** auth-security-reviewer

## Files reviewed
- `backend/src/api/dependencies.py`
- `backend/src/api/middleware.py`
- `backend/src/application/services/access_control.py`
- `backend/src/application/use_cases/audit_and_session.py`
- `backend/src/application/use_cases/list_groups.py`
- `backend/src/application/use_cases/manage_api_key.py`
- `backend/src/application/use_cases/manage_assistant_access.py`
- `backend/src/domain/access.py`
- `backend/src/domain/audit.py`
- `backend/src/infrastructure/auth/keycloak_token_verifier.py`
- `backend/src/infrastructure/auth/keycloak_group_directory.py`
- `backend/src/infrastructure/secrets/cipher.py`
- `infra/keycloak/nexus-realm.json`

## Integrations
- keycloak (OIDC realm, JWKS, admin REST API via client credentials)
- jwt (RS256 access tokens, verified with `cryptography`, no JWT library)
- postgresql (audit log, permissions, encrypted secret settings — via repositories)

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `backend/src/api/dependencies.py` | `get_token_verifier` | function | Builds traced Keycloak verifier per request (dependencies.py:97) |
| `backend/src/api/dependencies.py` | `get_current_user` | function | Parses `Authorization: Bearer`, verifies token, 401 on failure (:101) |
| `backend/src/api/dependencies.py` | `_unauthenticated` | function | 401 HTTPException with `WWW-Authenticate: Bearer` (:119) |
| `backend/src/api/dependencies.py` | `get_access_control` | function | Wires AccessControl with permission repo + AuditTrail (:139) |
| `backend/src/api/dependencies.py` | `get_secret_cipher` | function | Fernet cipher from `NEXUS_SECRETS_KEY`, read per request (:177) |
| `backend/src/api/dependencies.py` | `UnconfiguredLLMGateway` | class | LLM gateway stub raising when key/model missing (:269) |
| `backend/src/api/dependencies.py` | `build_llm_gateway` | function | Decrypts global LLM key per request, builds HTTP LLM gateway (:297) |
| `backend/src/api/dependencies.py` | `get_*_repository` / `get_*` | functions | ~25 DI providers for repos, gateways, settings |
| `backend/src/api/middleware.py` | `register_request_context` | function | Request-ID binding, root span, HTTP metrics/logging middleware (:23) |
| `backend/src/api/middleware.py` | `_route` / `_record` / `_request_fields` | functions | Route template, metrics emit, log fields helpers |
| `backend/src/application/services/access_control.py` | `AuditTrail` | class | Append-only audit writer, injects `user_name` into details (:25) |
| `backend/src/application/services/access_control.py` | `AccessControl` | class | Single façade over AccessPolicy; denies + audits (:58) |
| `backend/src/application/services/access_control.py` | `AccessControl.require_*` | methods | admin / llm / audit / curation / group-listing / assistant / document checks |
| `backend/src/application/services/access_control.py` | `AccessControl.manageable_assistant_ids` | method | Curator scope; `None` = all (admin) (:136) |
| `backend/src/application/services/access_control.py` | `AccessControl._deny` | method | Records `access.denied` and raises AccessDeniedError (:195) |
| `backend/src/application/use_cases/audit_and_session.py` | `DescribeCurrentUserUseCase` | class | Returns current user; logs `auth.session_started` (:30) |
| `backend/src/application/use_cases/audit_and_session.py` | `ListAuditEventsUseCase` | class | Admin-only audit query, self-audited (:65) |
| `backend/src/application/use_cases/audit_and_session.py` | `PurgeAuditEventsUseCase` | class | CLI retention purge, records `audit.purged` (:124) |
| `backend/src/application/use_cases/list_groups.py` | `ListAvailableGroupsUseCase` | class | Admin/curator list of Keycloak group names (:9) |
| `backend/src/application/use_cases/manage_api_key.py` | `SaveGlobalApiKeyUseCase` | class | Admin encrypts + stores LLM key, audited (:34) |
| `backend/src/application/use_cases/manage_api_key.py` | `GetGlobalApiKeyStatusUseCase` | class | Admin reads "configured" flag (:69) |
| `backend/src/application/use_cases/manage_api_key.py` | `GetGlobalApiKeyValueUseCase` | class | Internal decrypt of LLM key, no auth check (:87) |
| `backend/src/application/use_cases/manage_assistant_access.py` | `DeleteAssistantUseCase` | class | Admin deletes assistant + vector collection (:39) |
| `backend/src/application/use_cases/manage_assistant_access.py` | `SetAssistantGroupsUseCase` | class | Admin replaces assistant group bindings (:77) |
| `backend/src/application/use_cases/manage_assistant_access.py` | `ListDocumentsUseCase` | class | Curator/admin lists documents with restrictions (:121) |
| `backend/src/application/use_cases/manage_assistant_access.py` | `SetDocumentGroupsUseCase` | class | Curator/admin restricts a document to groups, syncs Qdrant (:157) |
| `backend/src/domain/access.py` | `Role` | enum | Realm roles `nexus-admin`/`nexus-curador`/`nexus-usuario` (:19) |
| `backend/src/domain/access.py` | `normalize_group(s)` | function | Strip whitespace + leading `/`, max 255 chars (:27) |
| `backend/src/domain/access.py` | `AuthenticatedUser` | dataclass | Validated identity (sub, name, roles, groups) (:47) |
| `backend/src/domain/access.py` | `AccessPolicy` | class | Pure deny-by-default access rules RN-21..24 (:79) |
| `backend/src/domain/audit.py` | `AuditAction` / `AuditResource` | enums | Audit event vocabulary (:12, :45) |
| `backend/src/domain/audit.py` | `AuditEvent` / `AuditQuery` | dataclasses | Audit record + validated query filters (:61, :83) |
| `backend/src/infrastructure/auth/keycloak_token_verifier.py` | `KeycloakTokenVerifier` | class | RS256 sig, iss, aud, exp, nbf checks; JWKS cache (:53) |
| `backend/src/infrastructure/auth/keycloak_token_verifier.py` | `http_jwks_fetcher` | function | urllib JWKS GET with timeout (:42) |
| `backend/src/infrastructure/auth/keycloak_token_verifier.py` | `_split` / `_b64decode` / `_parse_jwks` | functions | JWT parsing, JWKS → RSA public keys |
| `backend/src/infrastructure/auth/keycloak_token_verifier.py` | `_to_user` / `_realm_roles` / `_groups` | functions | Claims → AuthenticatedUser, filters unknown roles (:188) |
| `backend/src/infrastructure/auth/keycloak_group_directory.py` | `KeycloakGroupDirectory` | class | Client-credentials token + paged group tree walk, 60s cache (:52) |
| `backend/src/infrastructure/auth/keycloak_group_directory.py` | `http_post_form` / `http_get_json` | functions | urllib helpers (:28, :43) |
| `backend/src/infrastructure/secrets/cipher.py` | `FernetSecretCipher` | class | Fernet with key = SHA-256(passphrase) (:13) |

## Conventions observed
- **Naming**: snake_case functions, PascalCase classes, UPPER_SNAKE constants; Portuguese docstrings/comments, English error messages.
- **Error handling**: domain exceptions (`AuthenticationError`, `AccessDeniedError`, `DomainValidationError`, `GroupDirectoryUnavailableError`); `ValueError` for config errors; `LookupError` subclasses for not-found.
- **Logging**: stdlib `logging` with dotted event names (`auth.token.rejected`, `auth.jwks.unavailable`) + `extra` dicts; tokens/secrets never logged.
- **Async style**: synchronous throughout (sync FastAPI deps → threadpool); `threading.Lock` in verifier.
- **Type hints**: fully typed, `from __future__ import annotations`, frozen slotted dataclasses for inputs.

## Internal duplication
- `_utc_now` defined in `access_control.py:21` and `domain/audit.py:56`; third copy as lambda in `audit_and_session.py:136`.
- urllib JSON helpers: `keycloak_token_verifier.py:42` (`http_jwks_fetcher`) vs `keycloak_group_directory.py:43` (`http_get_json`); `DEFAULT_TIMEOUT_SECONDS = 5.0` duplicated at `keycloak_token_verifier.py:30` and `keycloak_group_directory.py:18`.
- `require_assistant_access` (`access_control.py:172`) and `require_document_management` (`:184`) are identical except for the policy predicate.
- `require_admin` (`:123`), `require_llm_configuration` (`:127`), `require_audit_access` (`:168`) are the same "admin-only" shape over three policy methods that all return `user.is_admin` (`access.py:98,113,117`).
- `UnconfiguredLLMGateway` returned for two different causes (`dependencies.py:316-319`) with one message that only mentions the API key.

## Cross-segment hints
- `get_token_verifier` (`dependencies.py:97`) calls `build_token_verifier()` per request; if `src/infrastructure/composition` does not cache it (lru_cache / module singleton), the JWKS cache is per-request and every request hits Keycloak's JWKS endpoint. Same for `build_group_directory()` (`dependencies.py:204`) — token + group cache would be lost each call. Composition segment must confirm.
- Authentication is per-route (`Depends(get_current_user)`), not global middleware (`middleware.py` has no auth). RF-40 ("every route except /health") relies on every router declaring the dependency — API-routes segment must inventory routes lacking it (also `/metrics`, which `middleware.py:18` treats as a public probe).
- `normalize_request_id` (observability segment) receives client-controlled `X-Request-ID` (`middleware.py:44`) that is echoed in the response and bound into logs/trace IDs — verify length/charset sanitising (log injection).
- Frontend segment: confirm token storage (in-memory vs `localStorage`) for the PKCE public client; realm does not enable refresh-token rotation (see findings).
- Database segment: confirm `assistant_groups` / `document_groups` rows cascade on assistant delete (`manage_assistant_access.py:54`), else a re-created assistant with the same id inherits stale bindings.
- Retrieval segment: RN-23 enforcement for chat depends on the Qdrant payload filter using `AccessPolicy.document_matches_groups`; DB-level restriction (`permissions.set_document_groups`) and vector payload are two sources of truth that must stay reconciled (see TOCTOU finding).
- `GetGlobalApiKeyValueUseCase` (`manage_api_key.py:87`) has no access check by design; the chat/route segment must ensure it is never reachable from a route returning its value.

## Specialist findings

### Auth flow inventory
| Flow | File:Line | Library | Token storage | Severity |
|------|-----------|---------|---------------|----------|
| Login (OIDC Auth Code + PKCE S256) | `infra/keycloak/nexus-realm.json:56-105` | Keycloak | SPA (frontend segment; not visible here) | med (default creds, no MFA) |
| Signup | `nexus-realm.json:6` | Keycloak | n/a — disabled | low |
| Password reset | `nexus-realm.json:7` | Keycloak | n/a — disabled | low |
| MFA | none configured | — | — | med |
| Refresh | Keycloak defaults (no `revokeRefreshToken`) | Keycloak | SPA | med |
| Bearer verification | `backend/src/api/dependencies.py:101`, `keycloak_token_verifier.py:78` | `cryptography` RS256 + JWKS | `Authorization` header | low |
| Session-start audit | `audit_and_session.py:40` | app | n/a | low |
| Service account (client credentials) | `keycloak_group_directory.py:112` | stdlib urllib | process memory | low |
| LLM key at rest | `cipher.py:13`, `manage_api_key.py:48` | Fernet | Postgres (encrypted) | med |

### Protected-operation inventory (this segment)
| Operation | Check | File:Line |
|-----------|-------|-----------|
| Delete assistant | `require_admin` | `manage_assistant_access.py:52` |
| Set assistant groups | `require_admin` | `manage_assistant_access.py:93` |
| List documents | `require_document_management` | `manage_assistant_access.py:135` |
| Set document groups | `require_document_management` (after lookup) | `manage_assistant_access.py:184` |
| Save LLM key | `require_llm_configuration` | `manage_api_key.py:49` |
| LLM key status | `require_llm_configuration` | `manage_api_key.py:80` |
| LLM key value | none (internal only) | `manage_api_key.py:99` |
| List audit | `require_audit_access` | `audit_and_session.py:78` |
| List groups | `require_group_listing` | `list_groups.py:21` |
| Describe current user | authentication only | `audit_and_session.py:40` |

### Findings
- **[high] Default credentials in realm import** — `infra/keycloak/nexus-realm.json:123-224`: five users incl. `admin.nexus` (`nexus-admin`) with password `nexus-dev`, `temporary: false`. Any environment importing this file (it is the only realm file) has a known admin password. Fix: separate dev-only realm file, or `temporary: true` + password policy; never import users in prod.
- **[high] Client secret placeholder can become a literal** — `nexus-realm.json:114` `"secret": "${NEXUS_BACKEND_CLIENT_SECRET}"`. If the env var is unset at import, Keycloak keeps the literal string as the secret → publicly-known secret for a confidential client holding `realm-management/query-groups`. Same pattern for `rootUrl`/`redirectUris`/`webOrigins` (`:67-77`), which then degrade to a literal path. Fix: fail the import/bootstrap when variables are unset.
- **[med] Group identity collapses on leaf name** — `nexus-realm.json:97` `full.path: "false"`, `access.py:33` only strips the leading `/`, and `keycloak_group_directory.py:138-140` returns leaf names only. Subgroups `/rh/gestores` and `/financeiro/gestores` both emit `gestores` → a member of one is authorised for assistants/documents bound to the other. Fix: use `full.path: true` end-to-end and keep the path (normalise only the leading `/`), and have the directory return paths.
- **[med] TOCTOU between reindex check and document restriction** — `manage_assistant_access.py:189-200`: `get_running()` check then `set_document_groups` with no lock/transactional guard. A reindex started in between copies the old (possibly empty) restriction into the new collection; after alias swap the restricted document is visible to every assistant user while Postgres still says restricted. Fix: take a row lock / advisory lock shared with reindex start, or have reindex read restrictions from Postgres at swap time.
- **[med] Weak KDF for secrets master key** — `cipher.py:17`: Fernet key = unsalted single SHA-256 of `NEXUS_SECRETS_KEY`. If operators set a passphrase rather than 32 random bytes, a DB dump allows fast offline brute force of the LLM key. No key rotation path (`MultiFernet`) either. Fix: require a real Fernet key (validate format) or derive with scrypt/HKDF + salt; support `MultiFernet` for rotation.
- **[med] No refresh-token rotation / session cap for public SPA client** — `nexus-realm.json:10-11` sets access lifespan 300s and SSO idle 1800s, but no `revokeRefreshToken`, `refreshTokenMaxReuse`, `ssoSessionMaxLifespan`, or `clientSessionMaxLifespan`. Stolen refresh tokens from the public client are reusable until idle timeout keeps sliding (default 10h max). Fix: `revokeRefreshToken: true`, `refreshTokenMaxReuse: 0`, explicit max lifespans.
- **[med] No MFA / password policy for admin role** — realm has no `passwordPolicy`, no `requiredActions`/OTP for `nexus-admin`, who controls permissions, the LLM key and the audit log. Fix: OTP required for admins via conditional flow; password policy.
- **[med] Authentication failures are not in the audit trail** — `dependencies.py:115` logs `auth.token.rejected` at INFO only; `AuditAction` (`audit.py:12-42`) has no auth-failure event and login success/failure lives only in Keycloak events with `jboss-logging` listener (`nexus-realm.json:12-16`) and `adminEventsDetailsEnabled: false` (`:18`). Role/group changes in Keycloak are thus not detailed anywhere. `SESSION_STARTED` (`audit_and_session.py:41`) is client-triggered (every `/me` call), not a real login signal. Fix: enable admin event details; ship Keycloak events to the same sink; add a rate-sampled `auth.rejected` audit/metric.
- **[low] Stale JWKS kept trusted indefinitely on fetch failure** — `keycloak_token_verifier.py:131-137`: on JWKS outage, `_fetched_at = now` and old keys stay valid; a key removed after compromise remains accepted for as long as the endpoint is unreachable. Fix: cap stale lifetime (e.g., 2× cache) before failing closed.
- **[low] JWKS fetch under global lock** — `keycloak_token_verifier.py:108-111`: network I/O (up to 5s timeout) while holding `self._lock` serialises all authenticating threads during refresh. Fix: fetch outside lock with single-flight.
- **[low] No `typ`/`azp` check, no clock-skew leeway** — `keycloak_token_verifier.py:90-103`: accepts any RS256 realm token with `aud` containing `nexus-api`. Today ID tokens are excluded only because `id.token.claim: "false"` on the audience mapper (`nexus-realm.json:88`); flipping that would make ID tokens valid API credentials. Zero leeway causes spurious 401s on clock drift. Fix: require `typ == "Bearer"` and optionally `azp == "nexus-frontend"`; allow ~30s leeway.
- **[low] No minimum RSA key size / `alg` per JWK** — `keycloak_token_verifier.py:172-182` accepts any RSA modulus and ignores the JWK `alg`. Low risk given trusted JWKS URL; add `key_size >= 2048` check.
- **[low] Non-auth exceptions escape as 500 from `get_current_user`** — `dependencies.py:113-116` catches only `AuthenticationError`; a token with a group name > 255 chars makes `AuthenticatedUser.__post_init__` (`access.py:63`, `:36`) raise `DomainValidationError` → 500 instead of 401. Fix: catch `DomainValidationError` in `_to_user` and convert.
- **[low] Existence oracle before authorization** — `manage_assistant_access.py:179-186`: document lookup precedes `require_document_management`, so unauthorized callers distinguish 404 (no doc) from 403 (doc exists). Fix: return the same error for both, or authorize first via assistant scope.
- **[low] Misleading denial audit actions** — `manage_api_key.py:80`: status *read* denial is audited as `llm_api_key.changed`; `require_admin` (`access_control.py:125`) records `resource_type=SETTINGS` with no `resource_id` even for assistant deletion/group changes, losing the target id in `access.denied` events.
- **[low] `user_name` in audit details can be overridden** — `access_control.py:52` `{"user_name": user.name, **details}`: caller-supplied details win. Put `user_name` last or in its own column.
- **[low] `sslRequired: "external"` and wildcard redirect paths** — `nexus-realm.json:5`, `:70`, `:77`: acceptable for dev; prod should be `all` and exact redirect URIs.
- **[low] Secrets key read from env on every request** — `dependencies.py:177-179`: missing key raises `ValueError` at dependency resolution for every LLM route (500, not a clear startup failure). Validate at startup.
- **Positive**: alg pinned to RS256 (`keycloak_token_verifier.py:80`, rejects `none`/HS*); iss/aud/exp mandatory; unknown roles dropped (`:207`); `sub` used as identity; unknown-`kid` refresh rate-limited (`:124`); deny-by-default policy centralised in `AccessPolicy`/`AccessControl` with denials audited; conversation ownership excludes admins (`access.py:121-129`); service account least-privileged (`nexus-realm.json:230-233`); brute-force protection on; implicit and direct-grant flows disabled; Fernet gives random IV + HMAC (no nonce reuse); LLM key never logged (`dependencies.py:308-315`).

## Concerns / smells
- Realm file mixes dev seed users with the only realm definition — default admin password ships wherever it is imported.
- Two sources of truth for document restrictions (Postgres + Qdrant payload) with a non-atomic check-then-write against reindex.
- Group matching by leaf name breaks isolation as soon as nested groups exist.
- Audit trail covers app actions well but has no authentication-failure or IdP-side (role/group change) visibility.
- Verifier/directory caching correctness depends on composition-layer singletons not visible in this segment.

## Refactor suggestions
- `infra/keycloak/nexus-realm.json`: split into `nexus-realm.json` (clients, roles, mappers, `full.path: true`, refresh rotation, password policy, `sslRequired: all`) and `nexus-realm.dev-users.json`; fail bootstrap when `${...}` vars are unresolved.
- `backend/src/infrastructure/secrets/cipher.py:13`: accept a proper Fernet key (or scrypt-derived with salt), wrap in `MultiFernet` for rotation; validate in app startup instead of `dependencies.py:177`.
- `backend/src/infrastructure/auth/keycloak_token_verifier.py:90-137`: add `typ`/`azp` checks, leeway, stale-key cap, out-of-lock single-flight refresh, min key size; convert `DomainValidationError` in `_to_user` to `AuthenticationError`.
- `backend/src/application/use_cases/manage_assistant_access.py:178-200`: serialize document-restriction changes with reindex start (advisory lock keyed on assistant id) and authorize via assistant scope before revealing document existence.
- `backend/src/application/services/access_control.py:123-193`: collapse admin-only `require_*` into one `_require(predicate, action, resource, resource_id)` helper and pass the target resource id so `access.denied` events always carry it.
