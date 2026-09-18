# Production-readiness change log

## TEST-COMPILED-02 — propagate frontend preview flag through canonical build

Committed44d597af, independent approval. Canonical Dockerfile omitted VITE_COMPILED_SCRIPT_PREVIEW_ENABLED even though the browser fixture requires compiled UI. Two contract tests failed against old Dockerfile/renderedstaging. Added ARG defaultfalse/ENV before frontend build; staging explicitly opts true. No production-default enabling, backend cohort still required. Focused+adjacent13tests pass0.79s; independent13pass1.44s. The a025 image built before this change cannot establish compiled UI proof; durable proxy/profile and real runner tests are separate ongoing work.

## SEC-RBAC-03 — Operator chat denies read-only memberships before effects

Committeda0253199, independent review PASS. Native stored direct/network viewers reproduced200 instead of403 (two failures, six allowed controls). POST `/api/operator/chat` now uses the separate write-role guard before capability checks, audit, processing, result writes or commit. Other routes remain unchanged. New cases cover revoked memberships, owner/network-owner/superadmin and read-only current-conversation GET. Existing fallback fixture mocks the separately verified write helper; assertions were not weakened. Agent22pass1.15s (`raw/operator-chat-rbac-green.json`); reviewer22pass1.08s, expanded44pass1.70s and adjacent24pass0.56s. This is PG15/local chat proof, not platform-wide mutation closure or deployment.

## DEP-PDF-01 — pin the PDF parser with compatibility coverage

Committedee777f59, independently reviewed. Host pypdf6.13.2 advisory matches and reachable uploaded PDFs motivated pinning6.16.1. New valid-text/encrypted/malformed PDF compatibility test and adjacent ingestion tests passed58cases with isolated target install and pipcheck. No shared-venv upgrade or denial-of-service exploit; this is advisory-based mitigation. The later full native suite asserted isolated6.16.1 and passed4319tests. Final image version/audit remain separate gates; temporary dependency target was lost across host interruption.

## TEST-FIXTURE-03 — finance ROI read/write seam in the full suite

Committed5e1ebe79, reviewed. First native aggregate91797c74 had4315pass117skip1failure because the ROI fake cursor stubbed only read authorization after production writes acquired a separate guard. Fixture now models both seams without weakening tenant queries. Added allowed read/denied write and foreign-business controls;26focused tests pass. Fresh clean5e aggregate:4319pass117skip5warnings296.79s, raw `native-full-backend-5e1ebe79.json` exit0. Skips still include safe Docker tests and seven intentionally disabled live-provider cases; this is not final PG16 image verification.

## SEC-RBAC-02 — agent blueprint viewer mutation boundary

Committed206c06ab, independently reviewed. Real native-PG Flask red: direct/network stored viewer creates a blueprint (201, one inserted row) instead of403/no row. Agent blueprint access now selects the existing write-role helper for mutating HTTP methods; only the exact non-persistent `/preflight` POST retains read access. Compiled/custom-process previews persist state and therefore require write authority. GET/HEAD remain read paths; stored blueprint/run business controls authorization, not just a request selector.

Native17tests include actual insertion denial, member/manager/owner/network-owner/superadmin controls, revoked/foreign denial, run/approval denial before runner effects, preflight200 with fail-fast write-verifier spy and unchanged counts, custom/compiled previews denied before effects. Scoped adjacent118passed2.80s; root independent finance+network+blueprint54passed4.17s (`raw/blueprint-viewer-root.json`). This does not close generic Operator mutations or every API's role matrix.

## SEC-WH-05 — WhatsApp replay admission and visible uncertainty

Committed91797c74, independently reviewed. Signed identical callback red reached AI processing and send twice. Existing canonical partial unique event key now durably admits `processing` before effects; completed duplicates skip, processing duplicates do not mutate the first operation. Process failures/malformed results and false/raised provider sends require fixed-reason reconciliation. No automatic replay or exactly-once claim: a process crash after admission remains `processing` and needs investigation.

Handler validates string/opaque provider identifiers without rejecting padded IDs. Per-message failures accumulate a batch response while remaining messages are processed; an early duplicate cannot starve later fresh messages. New superadmin-only GET `/api/webhooks/whatsapp/events` lists bounded attention state without payload, phone, provider key or text. It is an API/support view, not a completed operator UI or automatic provider-history reconciliation.

Independent review caught active-duplicate status corruption, batch starvation, missing send-exception tests, and unsafe test DSN/schema assumptions; all corrected before commit. Native test uses explicit loopback/test-named DSN, rejects libpq host overrides, UUID schema/finally cleanup and two real connections. Root47passed0.50s (`raw/whatsapp-replay-root.json`), including auth/identifier/batch/reconciliation/immutability/concurrency/tenant cases. Provider calls are stubs; no production schema change, send or deployment.

## TEST-E2E-03 — fail-closed native fixture subprocess

Committed618b00b6, reviewed. Native test helper previously accepted an arbitrary DSN, overwrote the caller's Python egress-guard path and could load ambient dotenv. It now requires a literal loopback, test-named staging DB with no URL query/hash; preserves guard-first PYTHONPATH, disables dotenv and removes inherited libpq service/hostaddr/options. Docker branches are unchanged. Red7cases; unit green7, typecheck/scoped lint pass and actual native CLI verified with hostile synthetic inherited service/hostaddr.

The first attempted fix blanked libpq variables; actual browser run exposed78fixture failures (`service file "" not found`) while36nonfixture scenarios passed. Those variables must be absent, not empty. Failed evidence remains; after correction the complete114-case run is111pass/3missing-runner-fixture failures. This helper hardens its subprocess, not the entire machine or arbitrary Python/C-library network access.

## SEC-RBAC-01 — finance viewer and stored-transaction write boundaries

Real native PostgreSQL HTTP reproduction against the pre-fix HEAD archive returned200 for a stored viewer's ROI write where403 was required (`/tmp/sec_rbac_head_red.log`, one failed test). A second reproduction showed that authorizing requested business A was insufficient: the same actor could mutate its own transaction belonging to B, where its role was viewer (`/tmp/sec_rbac_target_red.log`, actual200). An earlier missing-helper ImportError was a test-construction failure, not authorization evidence, and is not used for the verdict.

The read/tenant helper stays unchanged. A separate write helper checks active direct/network roles and preserves business owner, network owner, superadmin and existing non-viewer access. Finance mutations use it; GET/HEAD and the genuinely non-persistent import-preview POST retain read access. CRM preview remains write-gated because it persists status. Transaction PUT/DELETE recheck the stored row's business before mutation. Legacy NULL-business, user-owned transaction behavior is explicitly retained; this is not a redesign of legacy finance storage.

Independent review approved the package and final HEAD/libpq-guard corrections. **37 tests passed in1.80s** (`/tmp/sec_rbac_head_guard_final.log`): real SQL role/tenant/revocation matrix, real Flask ROI and transaction effects, preview/HEAD controls and adjacent routes. Native fixtures require a dedicated explicit loopback test DSN, reject host overrides and clean only their UUID schemas. Generic Operator/agent mutation roles and the entire platform endpoint matrix remain unfinished. No production access, data or provider configuration changed.

## SEC-SSRF-01 — pin contact-page connections to validated public addresses

The old collector validated DNS, then fetched by hostname through `requests.get`, permitting a new resolution at connection time. A synthetic pre-fix run reached the forbidden hostname-request sentinel (`/tmp/secssrf01-red-final.log`, exit1); no private host or provider was contacted. The collector now uses a bounded GET primitive that validates every resolved address and connects to a selected numeric public IP, retaining Host/SNI/certificate checks. Redirect destinations pass admission again. Other outbound clients are not covered by this change.

Independent review caught and required fixes for revalidation exceptions, declared HTML charset and literal IPv6 Host formatting. Final tests cover private/mixed/rebound DNS, second-resolution failure, HTTPS pinning/SNI, private redirects, charset fallback and size/resource-release behavior. **76 tests passed in 1.32s**, root capture exit0 in1.936s (`raw/ssrf-pinned-get-root-green.json`), after independent source approval. The first root run had75passes/one main-import configuration failure because its sanitized environment omitted DATABASE_URL; that failed capture is retained and was corrected by explicitly selecting the synthetic local test DB, not by changing application behavior. No Internet/provider/production request or deployment was performed.

## TEST-COMPILED-01 — explicit local profile and run-scoped admission

Removed historical localhost/container defaults and generic queue claim from the synthetic compiled-table proof. Explicit app/ingress/project/environment/DB arguments are checked against a local Docker endpoint, running labels, exact loopback port, shared inspected internal network and the selected app's `app` alias. Read-only fixed proxy source hash/entrypoint ties this audit profile to its app:8000 route; this is local configuration validation, not hardware/cryptographic endpoint attestation. Docker calls are bounded. Admission UPDATE targets only the created run/blueprint/business in queued state and keeps normal lease/attempt fields; actual runner execution is still required. Independent review and9purefake tests pass, including happy path and negative identity/proxy/network cases. Combined root restore+compiled20tests passed. Real app-integrated execution remains unverified because Docker storage failed; the temp audit proxy/profile also needs a durable reproducible runbook before general developer use.

## OPS-RESTORE-01 — fail-closed local disposable restore helper

Removed ambient `.env` loading, implicit latest-archive selection, default live DB and automatic Compose startup. The helper now requires an explicit trusted `.sql.gz` archive, exact new target/confirmation, local Unix Docker context, container/project/user; verifies running PostgreSQL service labels and every loopback binding; refuses an existing DB, then creates a fresh disposable one. `docker exec -i` is used only for the SQL stream, with `ON_ERROR_STOP`. Plain SQL remains trusted executable input, not a sandbox; the helper intentionally cannot restore production. Failed restore leaves only its newly created disposable DB for deliberate inspection, no automatic destructive cleanup. Independent review caught missing target/context guarantees, invalid `docker exec -T` and weak tests before acceptance. Final independent11fake tests pass; no real helper restore was run during local Docker failure. The earlier separate consistent-snapshot rehearsal is not evidence of this helper's execution.

## DATA-FIN-01 — contain per-row import SQL failure

Real PostgreSQL reproduction: duplicate pre-check sees no row, another transaction commits the same unique key, then the first import hits UniqueViolation and its next valid row fails InFailedSqlTransaction (red1failed0.36s). Each existing item insert now has a savepoint; failed items roll back that savepoint and re-raise to the existing row-error collector. Following valid rows and the batch outcome can commit. File/CRM callers and response/error semantics remain unchanged. Test uses standard isolated testcontainers and a UUID database with finally cleanup, not a fixed developer port. Independent review required and approved that portability/safety correction. Final root combined regression suite11passed12.78s (`raw/data-concurrency-root-green.json`). Entry-path concurrent conflict is proven; other item types share the wrapper but were not independently raced. No external CRM/provider operation or production data change.

## DATA-SVC-01 — serialize compression-draft apply

Two concurrent applies read the same unclaimed draft and created two active replacement services (real PostgreSQL red:1failed4.12s, `/tmp/datasvc01-red.log`). Apply now locks only the draft row before reading status or mutating services; the second request waits, then returns the existing idempotent result. Other draft reads are unchanged. Final portable testcontainer test holds the first real lock, observes the second PostgreSQL session waiting, then asserts two HTTP200s, exactly one `already_applied`, and one active replacement. Independent review rejected the initial host-specific fixture/weak green barrier; both were corrected before commit. Final builder1passed26.76s; main combined data+finance11passed12.78s (`raw/data-concurrency-root-green.json`,13.285s captured), with inherited no-egress guard preserved. Scope is same-draft concurrency; distinct drafts sharing services remain a separate contract question.

## TEST-SAFE-01 follow-up — nested no-egress guards

The ca8bdf0b whole-backend rerun exposed a test assertion error, not an escaped network request: the inherited read-only audit guard denied port8000 before the child guard could emit its own message. The test now independently proves the child's audit hook with an explicit `sys.audit` event (no connection), while the actual socket attempt must fail with one of the two exact approved guard messages. Arbitrary subprocess failure is not accepted. Normal and outer-guarded runs each passed5tests (2.89s/2.45s), `/tmp/localos-safe01-causal-fix.log`; main independently reviewed the diff. No runtime or guard was weakened.

## SEC-AUTH-01 — Inactive session revocation

Status: **FIX_PROVEN locally**, independent review passed. Not deployed in this audit.

- Central `verify_session` rejects inactive users by default before a protected route can mutate state.
- `/api/auth/me` uses a narrow diagnostic opt-in and retains `403 account_blocked`; normal guards retain their 401 denial. Login's blocked-account contract is preserved.
- Normalize boolean/legacy `False`, `0`, `"0"` once for both guard and returned payload. Independent review caught a first-patch inconsistency for text `"0"`; a real `/auth/me` regression test reproduced it before correction.
- No schema, password, session row or production data mutation. Active-session behavior stays covered.

Evidence:

- Initial red builder reproduction: 2 failed / 12 passed, inactive bearer could execute a protected mutation.
- Review regression red: 1 failed / 2 passed (`legacy_inactive_values`), then 3 passed after normalization. JSON evidence in task `raw/sec-auth-01-legacy-zero-{red,green}.json`.
- Root rerun: `venv/bin/python -m pytest -q tests/test_auth_email_case_insensitive.py tests/test_auth_user_routes.py tests/test_browser_session_security.py tests/test_network_member_access.py` → **42 passed in 5.21 s** (7.391 s captured command wall time).
- Independent reviewer: three principal files, **40 passed**, previous finding closed, no additional blocker in the scoped package.
- Focused Ruff F821 and `git diff --check` pass.

Limits: full backend/PostgreSQL suite and deployed behavior not yet verified. This fix does not close the separate role/tenant audit. Source rollback is possible but would reopen revoked-session access and therefore is not a recommended security mitigation.

## CI-TS-01 — Real app and tooling typecheck in both CI entrypoints

Status: **FIX_PROVEN locally**, independent review passed; no CI deployment or remote change.

Both fast/nightly scripts now invoke the canonical `npm --prefix frontend run typecheck`. Their former root `tsc --noEmit` command exited zero without checking referenced app/Node projects.

Regression tests use actual locked TypeScript, tiny isolated referenced projects, real npm and the current package.json typecheck script. They inject errors separately into app and Node code, prove the former bare invocation misses them, and verify both gates fail; healthy fixtures pass. Non-typecheck gate phases are stubbed, so this is not an execution of the entire nightly job.

- Red baseline: six failing contract cases (healthy invocation contract plus swallowed app/Node errors).
- Initial green / independent rerun: 6 passed in 73.34 s / 70.03 s.
- Independent review recommended exercising the real package script instead of reproducing it inside the stub. Implemented; strengthened suite **6 passed in 84.02 s**. Root inspected the revised fixture and bounded subprocesses.
- `bash -n` and `git diff --check` pass. Canonical actual frontend typecheck separately passed the clean baseline and the finance patch check.

No application behavior, schema or provider effects changed.

## SEC-WH-01/02 — Authenticate WhatsApp and business Telegram callbacks

Status: **FIX_PROVEN locally**, independent scoped review passed. Not deployed or registered with providers.

- WhatsApp requires explicit verify token and raw-body HMAC-SHA256 using `WHATSAPP_APP_SECRET`, before parsing or side effects. Invalid/malformed/Unicode signatures fail closed; missing challenge returns400. Compose forwards the secret to app; staging blanks it and the isolation validator rejects leaked values.
- Telegram uses canonical business UUID plus a domain-separated per-business secret derived from the stored bot token. Indexed tenant lookup precedes constant-time authentication; JSON, transport ledger, workflow dispatch and legacy processing happen only afterwards. Retired raw-token URLs return410; raw token header/query/body authentication is no longer accepted.
- Deployment requires an approved provider rebind with the documented secret header, and matching WhatsApp configuration. Bot-token rotation requires rebind. No provider configuration was changed here; this is an explicit rollout prerequisite, not a backward-compatible automatic production rollout.
- Red evidence reproduced unsigned WhatsApp/Telegram callbacks reaching mocked processing/send and the insecure default verification token. Additional malformed-input cases failed before correction.
- Root final regression/adjacent/config suite: **83 passed in 0.63 s**, 1.078 s captured wall time (`raw/webhook-security-config-final.json`). Independent reviewer reran the same set plus two Docker tests: **85 passed in 0.74 s**; staging-isolation check passed. No scoped blocker.

Residual work remains separate: replay/deduplication, legacy WhatsApp PII logging and token-bearing exception logging need their own reproduction and patch. Authentication alone does not prove idempotency or approval enforcement of every downstream action.

## UX-FIN-01 — Finance import follows the selected business

Status: **FIX_PROVEN locally**, fresh independent scoped review passed. Not deployed.

File, mapping, preview, confirmation, history and status are cleared on a business change. Preview/import/history requests capture their business/version, and stale success, error, finally and parent-refresh completions cannot populate the newly selected scope. Successful import and scope changes also clear the native file input, allowing the same file to be selected again.

- Deterministic deferred-preview and completed-preview/history tests reproduce the original cross-business stale state. Independent review of the first patch found the remaining native file input; its regression was red **2 failed / 2 passed**, then green **4 passed** after the input reset.
- Fresh independent run: `npm --prefix frontend test -- --run src/components/FinanceImportPanel.test.tsx` → **4 passed**, 4.31 s test-command duration. Worker app/Node typecheck and lint pass, with the pre-existing `auth_new.ts:115` warning.
- No backend write contract, money calculation or product layout changes. Other content/services/operator scope candidates are not closed by this fix. Final aggregate frontend and real-API scope checks remain required.

## DOCKER-PUBLIC-01 — Include both frontend builds in clean images

Status: **FIX_PROVEN locally**, independent scoped review passed. No production rollout.

The canonical Dockerfile now builds `build:all` and copies `frontend/public-dist` alongside the main `dist`. Both host artifact directories are excluded from Docker context, so a stale local public build cannot hide this failure.

- Baseline clean image lacked `/app/frontend/public-dist/public-audit/index.html`; the real public entrypoint returned404. New static regression was red2, then green with the existing context tests (4 passed).
- Fix built from a separate clean baseline archive containing only this packaging patch: **39.493 s** with cached dependencies, image `sha256:3dc995eb73758128a56c4c1e42e43f3ca61c9c6725c70b3f12329958b12276f7` (ARM64). Both image HTML entrypoints are nonempty, runtime UID10001, source nonwritable, debug directory writable.
- Isolated app returns **HTTP200** for public audit; synthetic seed and five-flow API smoke pass. Capture: task `raw/docker-public-{build,runtime}-green.json`; smoke log `/tmp/localos-readiness-staging-smoke.log`, exit0.
- Fresh reviewer passed both Docker contract tests and inspected independent runtime evidence. This does not claim final whole-product patched-image proof, AMD64 compatibility, browser-worker packaging or dependency upgrades; those remain separate gates.

## TEST-FIXTURE-01a — Restore PostgreSQL test preconditions

Status: **FIX_PROVEN for these fixture groups**, independently reviewed. Runtime code unchanged.

- Client-info's test-only schema now contains the business projection/access columns and membership tables actually read by the route. Seven baseline failures were setup drift, not seven product defects.
- CAPTCHA/expiry/resume tests use their own migrated PostgreSQL testcontainers instead of arbitrary environment DSNs/minimal shadow queue tables; they seed valid users and required `parsequeue.user_id`. The successful resume fixture satisfies the current parsed-card validator. Expected `delayed_auto` and final `completed` states were checked against the actual worker branches, not broadened into an allowed-status list. Test name now describes automatic CAPTCHA retry accurately.
- Sheets recovery tests reconnect using the same explicit `LOCALOS_TEST_DATABASE_URL` used by their isolated schema fixture. `connection.dsn` omits its password and caused five authentication failures before the provider-boundary assertions.
- Client-info/worker combined: **11 passed in 35.44s**. Independent worker rerun: **3 passed in 30.31s**, raw `worker-fixture-review.json`. Sheets recovery/queue: **16 passed in 2.68s**, raw `sheet-provider-fixture-green.json`; reviewer approved DSN/schema isolation.
- No application validation/permissions/schema changes, new skips, provider writes or production access. Remaining baseline hook/Telegram/browser/migration failures and final full-suite rerun are still open.

## DB-MIG-02a — Safely reverse the empty work-review schema

Status: **FIX_PROVEN for work-review revision rollback**, independently reviewed. The complete rollback chain is still failing on a separate creator-portal dependency; no production downgrade is authorized or performed.

The former no-op downgrade left `business_work_links.action_id` referencing `journey_actions`, preventing an older revision from dropping its table. The corrected downgrade acquires `SHARE ROW EXCLUSIVE` locks in a stable order before inspecting data, refuses to discard review/link/settings data, non-default review fields or work-journal actions, and only then removes this revision's empty objects/columns and restores its predecessor's flow constraint. No CASCADE. Populated installations require a reviewed recovery/compensation plan, not a forced downgrade.

- Existing full-chain migration test reproduced the retained FK. New real-PG tests verify empty upgrade/downgrade, five independent data guards and row preservation, using a UUID-named disposable database inside its own testcontainer.
- Root review identified a check/drop race in the initial patch. A deterministic concurrent INSERT immediately after the guard was red without locks: **1 failed in 12.30s**, `/tmp/localos-db-mig02-red.log`. With locks the writer blocks and cannot commit into the removed table.
- Final suite: **7 passed in 35.28s**, `/tmp/localos-db-mig02-locks-green.log`. Fresh reviewer checked transaction/lock lifetime, all lossy fields, exact predecessor constraint and scoped cleanup. Compilation/diff checks pass.
- Existing `test_web_tracking_postgres.py` now passes the original journey-actions obstruction but fails later at `DROP creator_collaborations`, whose newer creator-portal downgrade is also no-op. This is tracked next, not hidden by weakening the test.

## SEC-WH-03/04 — Respect replay admission and keep ingress logs secret-free

Status: **FIX_PROVEN locally**, independent scoped review passed. Not deployed.

- Telegram already had durable per-business event admission. The route ignored its `duplicate` / `legacy_reply_should_continue=False` result when `matched_count=0`, allowing a repeated callback to reach legacy AI/send. It now honors all three admission outcomes; genuinely unmatched new messages keep the existing fallback. No new inbox/table or migration.
- Webhook/send logs use fixed event names and exception class only; no provider URL, exception value/traceback, message body, phone or chat ID. Both outer handlers return constant failure JSON. This is a module-level fix, not a claim that all application logs are clean.
- Before patch: **3 failed / 25 passed** in `ingress_hardening_red`; duplicate reached legacy processing, HTTPError exposed synthetic token/PII, and outer traceback exposed secret text.
- Fresh independent current suite: **89 passed in 0.73s**, `/tmp/localos-secwh0304-review.log`, exit0. Reviewer identified a test-observation gap: capsys alone does not capture logging records. Root strengthened tests with INFO-level `caplog`, individual sentinel absence and fixed event/type assertions; final **89 passed in 0.62s**, 1.016s capture (`raw/webhook-replay-log-final.json`).
- Remaining scope: complete WhatsApp replay/idempotency and malformed event-ID behavior are not established by this Telegram route fix; downstream approval and whole-system logging audit remain open.

## DB-MIG-03 — Safely reverse an empty creator portal

Status: **FIX_PROVEN locally**, independent scoped review approved. No production migration.

The former no-op downgrade retained creator-portal foreign keys into older collaboration tables. The replacement locks all affected tables in a stable order, refuses rollback if any portal table or non-default collaboration review field contains evidence, and removes only this revision's empty objects in dependency order. Populated portal rollback requires backup/restore planning; no CASCADE or silent history deletion.

- Real PostgreSQL: empty rollback, retained relationship data, retained review evidence, and a writer racing between the guard and DROP. Root final run **4 passed in 19.35s** (19.936s captured wall), `raw/creator-portal-rollback-final.json`.
- Independent reviewer checked all eight new-table guards, all four lossy collaboration fields, predecessor constraint ownership, lock lifetime, trigger/function removal order and UUID-test-database cleanup. No blocker; broader guard-branch test parametrization remains a nonblocking coverage opportunity.
- This package fixes one dependency layer. The separately edited offer-distribution downgrade is required for the complete historical chain and is not signed off by this commit.

## UX-SCOPE-01 — Clear revoked dashboard context

Status: **FIX_PROVEN locally**, independently reviewed; not deployed.

Membership refresh now replaces a removed selected business with an accessible one, or clears current business/control scope and mode-specific storage on empty access / the existing API 403 contract. Route-private state remounts on business or network scope identity changes. Transient errors preserve the current context with a visible retry action; revision fencing rejects obsolete and overlapping refresh responses.

- Five tests cover A→B/private-state reset, empty membership, 403, transient failure/retry and late refresh after manual switch. Worker final **5 passed in 2.79s**; independent rerun **5 passed in 3.04s**. Corrected independent ESLint invocation exit0 (`/tmp/localos-ux-scope-01-lint.log`); its first combined command had a wrong lint working directory, not a test failure.
- Root aggregate app/Node typecheck exit0 in **39.149s** (`raw/frontend-scope-typecheck.json`); focused root lint exit0. Reviewer checked network→business fallback and backend response contract.
- Backend authorization remains authoritative; this does not replace server tenant/role checks or establish every child callback's safety.

## UX-JOURNEY-01 — Keep registration navigation stable

Status: **FIX_PROVEN in deterministic component tests**, independently reviewed; original real-API browser rerun is next. Not deployed.

React Router's search setter changed identity after query updates, causing the journey loader effect to run repeatedly. Late load/preparation responses could then rewrite the new route's URL. Use the existing stable-callback helper, cancel obsolete load completions, version pending preparation, and key content by journey token so another journey cannot inherit the previous result.

- Real-API baseline showed registration navigation returning to the start route. Corrected unit reproduction **2 failed / 7 passed**: four GETs instead of one, plus a late response changing `/login` query (`raw/journey-navigation-red-corrected.json`). Earlier attempts contained corrected test-selector mistakes and are not the causal evidence.
- Final **11 passed** (6.183s captured command), including late preparation and old-token response; independent combined journey/influencer run **13 passed in 3.92s**, with full app/Node typecheck exit0. Root focused lint passes.
- Registration parameters and approval behavior unchanged. Remaining browser failures include a stale success-copy assertion and separate compiled-staging prerequisites; neither is hidden by this runtime fix.

## UX-TOUCH-01 — Restore minimum influencer action targets

Status: source regression green and independently reviewed; real mobile geometry rerun remains. Not deployed.

The isolated mobile browser measured the influencer table's platform link / shortlist / reject controls at 36 / 36 / 32px tall, below DESIGN's 40px minimum. Their existing Tailwind minimum-height utilities are now `min-h-10`; layout, labels and mutations are unchanged.

- Targeted red **1 failed / 1 passed**, green **2 passed in 3.36s**; focused lint clean. Independent combined run **13 passed** and app/Node typecheck exit0.
- This is a narrow three-control fix, not a claim of whole-site accessibility compliance.

## TEST-E2E-02 — Align real-API browser harness with its contracts

Status: independently reviewed harness correction; full browser rerun pending.

- Browser fixtures/assertions describe Russian workflows; explicitly set `ru-RU` rather than relying on the default English browser locale.
- Registration previously expected obsolete success copy even when the screen showed successful creation and email confirmation instructions. Assert the actual POST is successful with `success:true`, then require the visible resend-verification action. Token continuity, email verification, action route and cookie checks are unchanged.
- Remove the compiled spec's independent hardcoded port18006. All staging specs inherit one base URL, with precedence `JOURNEY_STAGING_BASE_URL`, legacy `LOCALOS_STAGING_BASE_URL`, then localhost18000.
- Baseline corrected-locale run: **95 passed / 19 failed**, 330.392s; 15 registration failures include runtime navigation races and stale copy assertions, one mobile hit-area failure, three wrong-port compiled failures. Do not classify all 19 as product defects or claim they are all resolved by these harness changes.
- Compiled test still requires an actual approved sandbox runner result. Its fixture is not created by the basic staging seed; no skip or fabricated result added. The standalone old-port compiled script is separate follow-up work.

## DB-MIG-04 — Reverse empty offer distribution without losing history

Status: **FIX_PROVEN locally**, independently reviewed; no production downgrade.

The final no-op dependency layer now locks its affected tables and refuses to discard preference/run/recipient data, campaign review fields, recipient-linked child records or messages that cannot satisfy the predecessor's NOT NULL collaboration constraint. Empty schema reverses in dependency order without CASCADE; compatible pre-existing portal messages survive.

- Scoped final **11passed in30.69s**: four independent new-table guards, three campaign-field guards, standalone NULL-collaboration preservation, compatible predecessor-message preservation, empty reverse and concurrent writer.
- Root aggregate work-review + portal + distribution + existing web-tracking contract: **23passed in69.89s**,70.415s captured wall, `raw/migration-rollback-chain-final.json`. The original upgrade→downgrade→upgrade obstruction is now green on disposable PostgreSQL.
- Independent reviewer checked lossiness completeness, FK/DDL order, transaction lock lifetime and both extra message tests. Populated feature schemas intentionally fail closed; this is not permission to downgrade production or proof of restoring the real production backup.

## TEST-FIXTURE-01b — Preserve outreach and audience test invariants

Status: **FIX_PROVEN for these fixture groups**, independently reviewed. Test-only changes.

Founder outreach's source assertion now locates the actual `restoreTouchEdits` effect boundary after the earlier callback extraction; all persisted-vs-unsaved text and storage assertions remain. Telegram shared-audience fixtures now explicitly subscribe both synthetic businesses to `community_pulse`, satisfying the current visibility contract while still asserting A's decision does not appear for B.

- Red2failed7.25s (obsolete delimiter / ineligible empty result) →green2passed7.65s. Both full files **198passed in7.82s** in named tmux with local PostgreSQL and outbound network guard.
- Reviewer verified current service eligibility and tenant decision join, and that no runtime permission/behavior or assertion was weakened. Aggregate backend rerun and browser harness preconditions remain separate.

## Browser verification checkpoint after the frontend fixes

Both committed frontend assets rebuilt without .env (32.856s) and copied only into the verified isolated local staging app. **33real-API browser checks passed in94.759s** across desktop, laptop and mobile:15registration/email/action-continuity and18authenticated-page quality cases. This closes the original navigation and mobile geometry reproductions for this local build. Other staging specs, compiled runner fixture and final backend-inclusive image still need final aggregate verification.

## TEST-SAFE-01 — Quarantine the retired live API script

Status: **FIX_PROVEN locally**, independently reviewed. No application change or test-network effects.

Default pytest discovery explicitly excludes `tests/legacy`. The archived print-only API script no longer contacts an arbitrary localhost application for registration/login: both direct invocation and calling its old entry point fail closed with guidance toward isolated API tests. This intentionally retires an unsafe manual script; it does not turn a real failing assertion into a skip/pass.

- Four regression checks prove default exclusion, direct-entry refusal, in-process refusal and a no-egress sentinel. **4passed in3.14s**, `/tmp/testsafe01_hardened.log`.
- Root review identified that the first regression subprocess would itself call localhost if old source were restored. Child audit hooks now block connections before collection/runpy, and in-process tests block imports/socket calls before evaluating legacy source. Independent reviewer approved the strengthened boundary.
- Explicit pytest invocation of the retired file fails intentionally; the observed1failure is the expected fail-closed contract, not a pre-patch red reproduction. Remaining archived files are not counted as validated tests.

## Frontend aggregate checkpoint

Fresh committed frontend source, reused locked install: **570unit tests /122files passed**,176.591s captured wall; lint0errors/1existing warning14.728s; app+Node typecheck36.781s. Captures `raw/frontend-patched-{unit,lint,typecheck}.json`. Existing intentional error-boundary/jsdom console diagnostics remain; no unit failures. This aggregate plus both builds and33real-API checks is not a whole-project readiness sign-off.

## TEST-E2E-HARNESS — Isolate Python browser-test startup and requests

Status: **FIX_PROVEN locally**, independently reviewed; test infrastructure only.

Two browser regressions now require installed frontend dependencies explicitly, own a high loopback Vite port with strict binding, bound startup/diagnostics, and clean up only their process group on success or failure. Exact-origin browser interception fulfills only own-origin API and the frontend's canonical DEV `http://localhost:8000/api/*` without any network forwarding; all other origins/ports/protocols are blocked. UI/error-recovery assertions are unchanged.

- Red under outbound guard:1failed+1error17.47s, fixed old ports blocked as unrelated local services. The original clean archive also lacked frontend dependencies; missing preconditions were not product defects.
- Review found overbroad loopback mocking and orphaned Vite on failed startup. Both corrected; eight deterministic harness checks now cover allowed/denied routes and mocked failed-start cleanup, plus the two actual browser flows. Final **10passed34.24s**, `/tmp/e2e_harness_lifecycle.log`.
- README now lists the actual Node/frontend/Chromium prerequisites and intentional legacy-script quarantine. No auto-install, runtime feature changes or real localhost API writes.
- Separately, the full72 mocked frontend browser scenarios pass after the application fixes,112.311s captured wall, `raw/frontend-patched-mocked-e2e.json`. Their temporary audit config uses a dedicated strict port and refuses server reuse; API behavior remains mocked, not production proof.

## TEST-FIXTURE-02 — Exercise the real network-membership fallback

An isolated native PostgreSQL 15.15 cluster (loopback-only, fresh synthetic databases) enabled previously skipped Operator/finance/journal tests without touching the broken Docker store. The fixed `3fadbabd` archive ran 22 files: **704 passed, 4 failed in 54.71s** (`raw/native-pg-operator-previously-skipped.json`). All four failures were missing network schema in the journal fixture, reached after direct membership revocation; they are fixture defects, not demonstrated production authorization defects.

The journal fixture now applies canonical network/business-link and network-membership migrations. Five additional real-SQL cases check active manager/member, viewer, revoked membership and a different network; denied writes create no journal record. Existing PermissionError/HTTP403 assertions are unchanged. Independent review approved the test-only patch. The three affected files reran: **79 passed, 5 third-party deprecation warnings in 10.32s**, capture exit0 in10.958s (`raw/native-pg-journal-network-green.json`). This is PG15 evidence, not a replacement for production PG16 or the still-incomplete full backend run.

The complete same 22-file selection then reran from the same fixed archive with only the committed journal fixture replaced: **713 passed, 5 warnings in 52.89s**, capture exit0 in53.629s (`raw/native-pg-operator-fixture-green.json`). This isolates the causal test-schema correction; it does not include the subsequent finance-RBAC runtime changes.
