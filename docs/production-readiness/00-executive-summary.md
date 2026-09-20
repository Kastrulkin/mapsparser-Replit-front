# LocalOS readiness executive summary — working, not final

Updated 20 September 2026. This is a decision aid for an owner or potential
partner. It is not a production-readiness certificate, release approval, or a
claim that external providers have been exercised.

## Latest checkpoint

Private clean Python parity covers 133 distributions; frozen `5cc7c0cd` migrated
successfully and collected 4,910 tests. The initial full aggregate is retained
not green: 4,886 passed, 9 failed, 1 error and 14 skipped. Corrective captures
support 4,903 unique non-provider cases across runs, not one clean aggregate
green run; seven live-provider skips remain intentional. The unchanged frontend
checkpoint remains 642 units across 129 files with TypeScript, lint, builds and
integrity. Free space is about 5.8 GiB, below the separate 10 GiB image floor.
V2 preparation has not executed: its first script write was safety-rejected, and
root's guard/probe files are static-PASS preparation only. A new asynchronous
permission request is pending for preparation plus an isolated full test; restore,
deploy and deletion are excluded. Restore approval remains separate. See
[COMMANDS.md](COMMANDS.md) and [HANDOFF.md](HANDOFF.md); dated detail below is
historical and does not promote readiness.

## What LocalOS is

LocalOS is an operating layer for local businesses. It helps an owner or team
turn signals from maps, reviews, services, content, finance, locations and
partnerships into visible work, drafts and reviewed actions. The business keeps
control: publishing, outreach, payments, destructive changes and provider
writes require the documented human approval or manual boundary.

## What is materially stronger after this work

- Frozen current frontend4e33587d now passes all642 unit tests across129 files,
  TypeScript, lint (one known warning), app/public builds and asset integrity;
  independent evidence review passes. Existing exact dependencies were reused.
  This does not certify a clean install, browser/API, new backend changes or
  production. Fresh review found a media-fetch security path, now locally fixed
  in5cc7c0cd with279 guarded regression/adjacent passes and independent review;
  the intentional Telegram webhook transition still needs an approved cutover.
- Website context used by content plans now rejects private network destinations
  and unsafe redirects while bounding page size and redirect count. Local4e33587d
  has149 passing adjacent checks including25 focused cases and independent review;
  this is synthetic-network proof, not deployed certification. Latest local
  capacity is about7.08GiB; Docker is running without resets. Current backend
  dependency/runtime and image checks remain open; image headroom is still below
  the unchanged10GiB planning margin. Prior low-disk failures remain evidence.
- The shared business writing-style profile now requires write permission when
  changed, while permitted viewing and personal examples remain available.
  Local432f64a0 has a causal regression,19focused/92overlapping adjacent pure
  passes and independent review. This is not native-database or deployed proof.
- News generation now has three additional reviewed local protections: Telegram
  command chat requires write access; the legacy generator's crash is fixed
  together with business/source authorization and final-text validation; its
  database schema is verified rather than changed inside a request. Final scoped
  sets pass101Telegram/adjacent and73legacy/adjacent pure tests (overlapping,
  not174unique tests). Commits78102124,72fd27a9,3ee2279a are not deployed or part
  of the older full backend aggregate. Native database, current-image and real
  provider validation remain separate; generic Telegram chat is now writer-only.
- Today static decision/preference/empty-work labels now use ten-language copy
  in local7c374f1f: three causal failing tests become93focused/adjacent passes;
  TypeScript/lint and independent review pass. Server-supplied Russian action
  labels remain unresolved. On19September new build/full units did not run because free Mac
  space fell below the2GiB safety floor (~1.7GiB, with11GiB swap allocated).
  No deployed or fully translated Today claim is made.
- New content-plan checks reproduce and fix read-only generation and selected
  network-target authorization gaps. Localbe1b1a95 passes independent review and
  164isolated PostgreSQL/adjacent tests7.91s; permitted viewers can still read their
  own context and legitimate writers can generate. Concurrent role changes during
  generation, the complete permission matrix and production rollout remain separate.
- Publication preview and accessible Close labels now follow the selected locale
  in local67169692. Final focused51tests and full620frontend tests/129files354.85s,
  TypeScript, lint, build and asset integrity pass. This is not a new browser or
  current-image result. User-enabled production IAB login was observed read-only;
  Today still mixes Spanish static copy with English fallbacks and Russian
  server-supplied action labels. That separate locale debt is not hidden by this fix.
- The earlier frozen backend checkpoint passed4,751tests in652.30s,
  with7deliberate live-provider skips and6dependency/configuration warnings.
  The run includes isolated PostgreSQL and browser regressions; owned test
  resources were checked after completion. It is not a current release-image,
  production, or complete presenter-rehearsal result. Concurrent source changes
  that appeared later are not covered by that frozen run.
- The partnership demo seed now supplies an explicitly unconfirmed synthetic
  audience-overlap explanation using the actual drawer contract. Two regression
  tests and44overlapping adjacent tests pass. The exact retained demo record
  was added without resetting other data, preserved on repeat, and verified in
  the current frontend drawer. Complete presentation rehearsal is still open:
  browser file selection and remaining test-proxy compatibility gaps interrupt
  it. Preview finalization is now causally fixed and verified in a real helper
  smoke plus the latest partial walkthrough. No finance data changed; this is
  not a completed end-to-end presentation.
- Password reset pages no longer print raw reset credentials into the browser
  console. A synthetic regression preserves the reset request and success while
  confirming no credential output;28focused/adjacent checks, the rebuilt asset
  and full616frontend tests pass. This reviewed local change does not certify
  the deployed version.
- Callback alert selection now rotates through eligible businesses rather than
  repeatedly selecting the same first100. A101-business reproduction fails
  before the change and the29-test bounded set passes afterwards; independent
  review accepts the local fix in7bb9f996. The cursor resets on worker restart;
  durable/global scheduling and a current release image remain separate.
- Review-draft labels and Copy/Copied feedback now use locale strings. The
  frontend unit run passes615tests; a subsequent TypeScript check found four
  duplicate translation keys. Removing only those identical duplicates restores
  TypeScript and4focused locale tests; lint has0errors/1existingwarning, both
  frontend builds and their199/12reachable-JS integrity checks pass. A separate
  correctly configured cookie-mode build passes the review/copy scenario on
  three viewports/languages in5.951seconds, including exact clipboard content.
  It uses a historical synthetic backend, not current release or all-language proof.
- Interrupted callback delivery now has a locally verified quarantine and
  explicit reconciliation path, with no alert-triggered automatic replay in
  the deployment smoke. The final focused set passes25tests; separate API/schema
  validation passes73tests (overlapping coverage, not98unique tests). This newer
  source is covered by the new6eec full backend aggregate, but not a current image.
- Local regression tests now cover blocked-account sessions, authenticated
  provider callbacks, several stored-role and business-boundary checks, safer
  outbound lookup, and transaction/replay protection for internal changes.
  These reviewed fixes are not yet deployed by this audit.
- A further104-test native/adjacent package verifies review mutations and
  mobile-action confirmation against stored roles and subscription state.
  Read-only users cannot enter mutation executors; legitimate member controls
  and idempotent replay are preserved in reviewed local272794a4.
- An opt-in digest-referenced application release profile and separate isolated
  real-API CI job are implemented and contract-tested. They have not been
  deployed or run as a hosted workflow; configuration checks are not runtime
  release evidence.
- The earlier backend browser checkpoint passed **117 of 117** scenarios with
  backend `272794a4` and byte-verified unchanged frontend artifacts, in a
  261.028-second command capture. Three compiled-runner cases remain covered
  only by the earlier **120 of 120** checkpoint (227.301 seconds, `20431224`
  frontend over `f0cc` backend). Neither is a final current immutable image,
  customer or production run. A fixed-port console filter limited that run's
  console-error coverage. It is now fixed in21focused unit tests with scoped
  type/lint checks and independent review. The selected review/finance follow-up
  now passes6/6 on three viewports at archived641; it is not a117-case rerun.
  The old result is not retroactively promoted. Page-error checks remain active.
- A clean backend aggregate at earlier `272794a4` recorded **4,728 passed,
  7 skipped** tests in656.63seconds, including native and Docker PostgreSQL integration.
  Only live-provider checks were intentionally skipped. Earlier environment
  failures were reproduced and corrected without product changes. Independent
  review accepts AC4 in its isolated local scope; current image and broader
  security inventory remain separate gates.
- Frontend checkpoint3dca5fda passes591unit tests,72mocked browser scenarios,
  full TypeScript and lint with0errors/1existingwarning. Both builds passed;
  the original capture then failed a wrong artifact-path assertion. A separate
  reviewed source/HTML/asset proof passes; the original exit1 is retained, not
  relabeled as an all-green aggregate. Current cleanf0cc
  historical Docker image builds both frontends with Node22 and passes nonroot/offline/
  read-only Chromium and Python dependency-consistency smoke checks.
- A controlled synthetic recovery exercise compared all 288 tables, data,
  schema objects, grants and sequence state after restore. It demonstrates a
  local helper path, not recovery of a production backup.
- The reviewed browser-enabled image is 22.2% smaller by Docker-reported size.
  That reduces storage pressure; it does not demonstrate faster application
  requests or higher capacity.
- Publication uncertainty now has reviewed local protection against duplicate
  sends and a receipt-based reconciliation interface. The scoped package passes
  237 backend tests. Mobile calendar containment and focus restoration now have
  22 targeted UI tests plus the passing120-case real-browser checkpoint,
  including receipt reconciliation and duplicate-confirmation protection in
  all three viewports. Final whole-source/release proof remains separate.
- Repeated cold-request measurements cover five journeys, with 50 samples per
  revision. The fixed version passes all 750 requests; the baseline consistently
  fails business-data retrieval. Other journey medians are nearly unchanged,
  so these results do not establish a general speedup or production capacity.
  A later bounded prepared dashboard profile also passes44/44requests; its
  in-process local scope is explicitly not HTTP server capacity evidence.
- A bounded current-backend HTTP profile passed **240 of 240** semantic reads
  over 64.28 seconds, with four synthetic tenants and ten resource snapshots.
  Browser observations add 60 successful local page loads, with median visible-
  control readiness of 325–372 ms. That browser profile uses the historical
  backend and unchanged frontend. Both profiles have independent count/quantile
  review; neither establishes production capacity or a general speedup.
- Accessibility work closed the observed agents-label contrast failure in the
  local browser checkpoint. The product still needs broader slow-network,
  large-data and demo rehearsal coverage.

Evidence and scope are recorded in [PROGRESS.md](PROGRESS.md),
[HANDOFF.md](HANDOFF.md), [04-performance-report.md](04-performance-report.md),
and [05-ux-review.md](05-ux-review.md).

## Current maturity and practical use

The product has meaningful locally verified foundations: browser journeys,
tenant-aware business workflows, reviewed action boundaries, migrations and a
synthetic restore path. It is suitable for continued controlled development,
synthetic demonstrations after rehearsal, and an explicitly scoped internal
pilot only when its release gates are met.

It is **not yet ready to be represented as production-ready**. No audit
deployment, production database change, production recovery rehearsal, real
provider send or publication occurred in this work.

## Remaining release gates

- Confirm revocation status for historically exposed credentials without using
  or disclosing them.
- Finish the current-source, dependency, image and log scan/triage work.
- Complete current immutable-image/compiled-runtime testing and realistic
  capacity/queue measurements. Current native real-API tests and a bounded
  sustained HTTP profile now pass; tiny-fixture plans are not capacity proof.
  A genuine fresh
  whole-diff review found further social-role/approval-boundary gaps, now fixed
  in independently reviewed local packages. Fresh whole-diff review at272794a4
  found no additional reproduced P0/P1 regression in its stated coverage;
  broader release verification still remains incomplete.
- Rehearse the partner demo and retain only its synthetic, manually controlled
  path and fallbacks.
- Complete final release verification of the locally reviewed publication-
  reconciliation and approval-binding packages. Commit13c1f36a binds actual
  provider recipient/account and media metadata; arbitrary remote object-byte
  immutability and final release proof are not established.
- Obtain separate authority and proof before any production backup-restore
  rehearsal, release, migration or provider configuration change.

The detailed evidence-backed list is [09-residual-risks.md](09-residual-risks.md).
The controlling decision remains the original Definition of Done, not this
summary or a numerical score.

## Investment focus

Near-term investment should prioritize reliable release/recovery evidence,
publication release verification, supply-chain scanning and measured performance
before broad feature expansion. Once those gates close, the next product-value
work is a rehearsed owner-facing demo and incremental simplification of the
largest work areas, protected by their existing regression coverage.
