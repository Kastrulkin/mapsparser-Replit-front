# UX and browser verification — working evidence

## Review the version being approved — 20 September, parent191488ba

Owner task: review the saved message and destination that approval or pilot
launch actually targets. Transient previews and unsaved text/channel/schedule/
sender edits now block approval, pilot start and resume. Saving/applying a
recommendation reloads the exact new ID, showing canonical saved text/recipient
instead of transient POST output. Missing/failed reload remains blocked. A
secondary discard action and version selector explicitly restore saved review.
Pause/cancel/reply sync and separate pilot confirmation remain unchanged.

Causal7fail/1pass becomes40focused passes (14new,20scope,6existing), including
canonical B approval/pilot routing, cancel-confirm, learning/reload errors and
resume after discard. Independent bounded source/targeted review PASS; final
broader checks are reconciled in COMMANDS. Native controls/labels and established
styles are retained; no new keyboard/focus mechanism. Browser/mobile accessibility
and actual provider delivery are not certified by jsdom. The earlier source-only
consent note below is superseded by this bounded local correction, not deployment.

## Campaign context continuity — 20 September, parent03ef38f6

Owner task: review only the currently opened lead, its recipient and campaign.
Deferred old campaign/preview/save responses replaced the newer card; old busy
state blocked new controls. Causal4fail/1pass; final26 targeted cases pass after
keyed state and lifetime fences. Tests cover exact current approval URL,
immediate old UI removal, A→B→A, close/reload callback, StrictMode, same-key draft
preservation, business/segment changes and stale resolve/reject during B busy.
Original controls, styling and endpoint payloads remain unchanged.

Independent bounded source review PASS; quality/build/aggregate reconciliation
is in COMMANDS. This is jsdom/mocked API evidence, not new-build browser/mobile
or production proof. User-authenticated IAB Today was observed read-only; it
still combines Russian, Spanish and English. No production action was submitted.
Separate source candidate UX-CAMPAIGN-CONSENT-03 needs causal proof: an unsaved
preview can obscure which saved version the approval button targets.

## Campaign recipient visibility — 20 September, parentca0c3d36

Owner/operator task: check where each campaign message will go before approval.
The builder previously showed channel and message but omitted destination.
Saved touches now project the selected contact's normalized address by exact
UUID; both preview branches include recipient on each touch. The existing UI
shows it as escaped text beside the message, or warns when it is absent.
No client guess from other contacts, new control, focus behavior or consent
change. Long destinations wrap with existing typography/style conventions.

Actual causal UI5fail/1pass becomes6passes; backend6fail/1pass becomes288pure
passes including adjacent contracts. Independent bounded review PASS. The test
matrix includes saved, fresh preview, absent address, markup escaping and a
normally resolved workstream switch. Full frontend/build/quality results are in
COMMANDS. This is not native SQL, browser/mobile layout, localization or an
async late-response proof. An old request overwriting a new workstream remains
a separate source-only candidate; it requires a deferred-response reproduction.
No production approval, send, preview generation or form submission occurred.

## Exact outreach review — 20 September, parent79d7b227

Operator task: check every message and its destination before consenting.
Previously the advanced summary showed only count/type, while the main panels
offered confirmation without this exact draft snapshot. ApprovalPayloadSummary
now shows every stored review_text and recipient/channel; EmployeeTestResultPanel
and AgentApprovalDecisionPanel place it before their actual controls. React
escapes content; text/newlines are preserved. Legacy/incomplete review warns;
the stale response explains reject/reprepare instead of silently accepting edits.
Final16tests/3files include both controls with spy callbacks, six-item visibility,
text priority, markup escaping, missing snapshot, unchanged generic summary and
error recovery. No real approval/send is performed by these tests.

Read-only authenticated IAB Today was confirmed again after the user logged in;
Spanish/English/Russian labels remain visible on that deployed artifact. No
production form/action was submitted. That observation is not a new-build
browser test, linguistic/mobile/accessibility audit or proof of the local fix.

## Managed Progress slice — 20 September, parent2fac7241

The owner/manager needs to understand the listing state, choose a goal, act on
the next correction and read the measurement in the selected language. The
confirmed failure was a Spanish managed-card scenario rendering Russian system
headings/action/evidence text. The direct-focus branch, managed panel and audit
details now select copy by explicit API codes in all10supported locales.
Business names, provider brands, source identities and numeric facts remain
data, not translation keys. Dates/numbers are locale-formatted; unknown codes
fall back safely, including prototype-like values. RU legacy raw copy is kept.

The causal UI capture fails1test/4pass; final focused capture passes15tests in
9.62s. It covers the actual Russian API-text fixture, Spanish direct action,
decision/evidence, audit-open focus, error/empty state, scoped goal PUT and all
10locale keysets/17action codes. Backend212pure contracts pass. Local app build
and199JS asset integrity pass; full frontend676tests/131files passes305.19s.
Independent bounded source review PASS. These
are jsdom/mocked-contract checks, not real API, browser layout or native-speaker
certification. Goal confirmation is exercised only against a request mock.

Shared JourneyActionCard remains untranslated in the normal managed-action
branch. Replacing it with the localized direct-focus navigation card would lose
its execution/approval behavior; it needs a separate presentation-only contract.
Thus whole UX-LOCALE-07 stays PARTIAL. User-authenticated IAB Today was rechecked
read-only; live mixed copy is the deployed version, not this unshipped build.

## Today API-owned copy slice — 20 September, parent 625a5d15

The owner/manager's task is still to choose the next action on Today. The
existing primary action, decision/continue/results sections, navigation and
approval boundaries are unchanged. Seven sheet-write status descriptions and
the generic Open button now have explicit additive API display codes and a
ten-locale frontend dictionary. Raw API text remains available to old clients
and Telegram; user titles, campaigns and drafts never become translation keys.
Unknown/missing/prototype-like codes preserve the existing fallback path.

Causal RED: 8 backend failures/4 passes and 1 frontend failure/30 passes.
GREEN: 42 pure backend/API/mobile tests and 109 frontend adjacent tests/8files.
Independent static review PASS. App/public builds and reachable-asset integrity
PASS (199/12 JS assets). Full667units/130files PASS. Typecheck caught one
test-query API mismatch; after the full run only that test option was corrected,
then31TodayPage tests and app/node TypeScript/lint passed. App code was unchanged.
Lint retains one existing warning. See COMMANDS for exact captures and limits.

This is PARTIAL UX-LOCALE-07, not complete localization: focus-action and other
unkeyed API/system copy remain. Ten-language coverage is not a native-speaker
linguistic review. Production Today was observed read-only after login and still
shows the previously reported mix; no deployed revision/new-build browser proof
or live preference/provider mutation follows from that observation.

## Today static copy fix — 19 September, 7c374f1f

The three static surfaces observed/traced below now have causal local proof:
3failed/24passed before,93focused/adjacent tests after, TypeScript and lint pass,
independent reviewPASS. Ten declared locales have complete typed operational copy;
RU/EN behavior and actual API strings are preserved. Spanish tests check the
decision section, preference summary, empty-content CTA, scoped GET/noPOST and
navigation. This is the static subset only: Russian server action labels remain
an unresolved localization contract. No arbitrary business-content translation.
The historical capacity block was superseded on20September by642frontend units,
TypeScript/lint and both builds for tree0af96cd4. Current API-copy slice is above;
deployed-browser verification remains open. See COMMANDS for scoped captures.

## Read-only production Today observation — 19 September

After the user reported login, root selected the existing IAB tab on
`https://localos.pro/dashboard/today` and read its accessibility tree, without
navigation clicks, refresh or mutations. The authenticated Today screen and
SuperAdmin badge were present. No session/cookie/token was extracted.

UX-LOCALE-07: Spanish `Hoy`/`Actualizar` appear beside static English
`Needs your decision`, its instruction, and `What to show first on Today`.
Independent bounded source trace identifies RU-vs-English literals at
TodayPage.tsx:294/366 bypassing existing todayPageCopy. This is not fixed by the
review/publication packages. Next local regression should render Spanish Today
with decision/preference fixtures and require Spanish static labels; no live
preference changes are needed. Russian operational title/button text comes from
the API and remains unchanged by localizedGrowthText for Spanish; its semantic
translation contract is separate, not assumed to be user-authored content.
The observation proves this display defect, not production API health or current
deployment identity. Subsequent static-subset proof is recorded above.

## Publication sheet labels — 19 September, 67169692

UX-LOCALE-06 is locally FIX_PROVEN. The owner's task is to review a publication
and close it without saving or sending. The real non-demo ContentPage sheet
hardcoded `Preview`; its shared SheetContent supplied an English accessible
`Close`. Five focused RED failures reproduce both missing localized labels.
The fix adds preview/close copy for all ten languages and an optional scoped
SheetContent label, preserving the existing default for other callers. It does
not change the generic Dialog, API requests, publication actions or focus logic.

Exact final focused capture `content-sheet-locale-green-typed-20260919.json`
passes51tests in8.83s (capture11.069804s). RU/TR component cases verify labels,
button close and no writes; calendar/list/nearest Escape cases retain invoker
focus, and primitive tests cover default/custom labels and no DOM prop leak.
The full frontend passes620tests/129files354.85s (capture356.870512s). Typecheck,
lint(0errors/1existing warning), build and199-JS-asset integrity pass. Two
independent scoped reviews pass. Earlier mock-history and unsupported test-query
option failures are retained, not hidden. See COMMANDS for exact captures.

No current browser, full-sheet all-language, production or release-image claim:
other real-sheet strings still contain hardcoded Russian. The new standard-config
cookie build is separate from the older envDir:false demo artifact. Backend
content scope authorization is a distinct locally proven packagebe1b1a95.

UX-LOCALE-05 is locally fixed at focused component scope. The initial locale
RED recorded3failed/1passed in7.35s (capture10.116326s, exit1/no timeout or
truncation): RU/EN/EL lacked the expected user-facing manual-draft heading.
The first GREEN instead exposed a test ambiguity (two legitimate Generate
buttons),3failed/1passed in3.73s; it is retained as a test failure, not an app
failure. The first full unit attempt remains **not accepted**:
612passed/3failed across127files in310.11s (capture311.826s, exit1; stderr
truncated). A separate Copy RED then recorded2failed/2passed in4.08s, showing
the EN/EL Copy leak while RU's existing control and clipboard behavior passed.
The Copy-enabled pre-dedup focused component set passes4/4 in4.08s
(capture7.066627s), with matching hashes and independent review PASS; the
exact-current post-deduplication focused proof is recorded separately below.

The current component reuses the existing localized `generate` and
`proposalLabel` copy, and adds a localized manual-publication hint plus
Copy/Copied feedback in all ten supported locale files. Focused runtime
assertions cover RU/EN/EL only: persisted draft text, manual and per-review
controls, clipboard feedback, and zero API writes. This changes no API or
manual-publication behavior and does not verify every locale in the browser.

The broader frontend unit run immediately before the four identical locale-key
deduplications passes615tests/127files in307.53s (capture309618.819ms). It is
not silently extended to the exact deduplicated source: a subsequent typecheck
RED exits2 in37740.933ms with TS1117 for duplicate `copy` keys in RU/EN/EL/TR.
After the minimal deduplication, typecheck passes40.163984s; the focused locale
set passes4/4 in3.79s (capture5.355626s), lint has0errors and one existing
warning in14.842858s, and app/public builds pass15.37s/7.26s
(captures16.788649s/8.344871s). App/public artifact integrity passes199/12.
The app build retains third-party PURE and external-outDir warnings. The first
private browser attempt failed preflight in1.382478s before login/browser because
the harness assumed compiled-pilot flags were false while the retained fixture
has both true; no three-viewport or product result is claimed.

The corrected cookie-auth browser check then passes **3/3 scenarios in
5.950617s**, capture `review-locale-browser-cookie-20260919.json`, exit0 with no
timeout or output truncation. It uses the current built frontend against the
historical synthetic `f0cc182a` stage: desktop RU, laptop EN and mobile EL each
show the localized draft card and exact copied draft text. All three record zero
page and console errors, zero browser mutations/direct-stage/external requests,
unchanged pinned artifact manifests, and fulfilled browser/Vite cleanup.
Synthetic login is an explicit three-POST prerequisite; this is therefore not a
claim that the run made no database writes. It does not recertify the current
backend, image, migration state, every locale, or the rest of the review flow.

The two intervening browser failures remain evidence rather than product
regressions: `review-locale-browser-retry-20260919.json` is a 13.470579s heading
locator failure, and `review-locale-browser-diagnostic-20260919.json` is a
12.932163s diagnostic run that proved login while retaining the same missing
heading/no-API result. The successful cookie build corrected only the harness's
documented `VITE_BROWSER_COOKIE_AUTH_ENABLED` setting; its build passes17.371317s
and subsequent 199-asset integrity check passes. It is not an application-flow
or backend fix.

19September managed-browser check: explicit business selection, loaded maps,
review/manual-publication boundary, content sheet and finance preview/apply/
duplicate retry were actually exercised on retained synthetic38019 staging.
Finance added two completed import-history batches, each0imported/2duplicates/
0errors; both earlier batches remained visible. No provider writes or reset.
Partnership opened but its current fixture did not expose the intended overlap
reason, so demo08 remains incomplete. Raw `managed-browser-demo-20260919.md`
distinguishes UI observations from DB-ID proof and tool delays from demo time.
The former mixed-language ReviewReplyAssistant labels (`Quick Generator`, raw
`draft`, and hardcoded Copy feedback) are addressed only by the focused local
change above; broader UX and browser evidence remains separate.
Bounded managed-console reads returned no warning/error entries; they are
separate from the automated collector evidence and current image proof.

TEST-E2E-04 browser follow-up is now complete: archived `641ec5e3` passed the
two owner reviews/finance scenarios on desktop, laptop and mobile, **6/6 in
22.0s** (48.938396s capture, exit0, valid=true, no timeout/truncation).
`raw/native-six-direct-v8-641ec5e3.json` records the dynamic API/frontend origins
51026/51027. Independent reconciliation confirmed the fresh synthetic DB was
dropped and all six recorded process groups were absent. The run predates the
callback source patch; it is not a 117-case rerun or current-image proof.
Initial readiness connection refusal and the optional popular-queries warning
remain in the evidence. Raw stdout contains synthetic fixture login/token
fields despite its redaction flag; retain privately, do not share unredacted.

18September16:54UTC: TEST-E2E-04 replaces the two owner-journey collectors'
fixed18000 filter with the configured origin. Causal unit RED8fail/7pass,
GREEN21pass, strictTS/lint and independent review pass. At that checkpoint no
browser rerun had occurred; the six-case follow-up above now covers the selected
flows. The historical117-case checkpoint retains its console-coverage limit.
Warnings, known third-party console errors and request/HTTP failures without
a console/page error are outside this collector's contract.

After15:30UTC: independent exact-criterion review accepts AC3 in its bounded
local scope. Clean install remains applicable because package manifests/lock
are unchanged; exact-source frontend591units/72mock browser/TS/lint/bothbuild
stages plus separate artifact proof and current117real-API cases cover the
required critical flows, tenant negatives and tested adverse/keyboard/focus
states. That does not claim all-page accessibility or current immutable-image
proof. Six additional login/finance screenshots show no observed overlap;
60observations have zero page errors/overflow on historicalf0ccbackend.

Latest18September15:16UTC: exact272794a4 native backend with source/manifest-
verified unchanged frontend passes117/117 across desktop/laptop/mobile,
capture261.027621s exit0/untruncated. Only3compiled-runner cases excluded and
remain the separately historical proof below. Initial114pass3fail was temporary
maps-source omission; canonical yandex_maps plus static preview fixes launcher,
not app/tests. At that run, the owner reviews/finance console filter hardcoded18000,
so the dynamic-port result does not establish global absence of console errors;
uncaught page errors and other existing suite assertions remain exercised.
No real provider writes; no final immutable image, demo or capacity claim.

Latest local check18September10:39UTC: reviewed20431224 frontend over isolated
f0cc backend completes **120passed**,227.301s,exit0/no timeout. It includes
real stored publication receipt, duplicate-confirmation protection, bounded
Month/List layout and Escape-to-invoker focus across desktop/laptop/mobile.
The preceding layout-only117passed/3failed run248.788s remains preserved:
its three new failures led to the scoped focus fix and three unit regressions.
This separately synced frontend is not final immutable-image evidence.

Earlier checkpoint: frontend8ebec5ca on isolated4a8backend, **114/114real-API browser tests pass215.263s** after clean build27.414s. All3viewports passed the Agents contrast check. Causal target was EmployeeWorkspaceSection title `Готовность процесса`; the earlier workflow-graph opacity change was adjacent and the first rebuilt5c1 rerun remained111/3. Both red captures retained.

Scope: existing LocalOS task flows, not a redesign. Latest checkpoint18September2026: clean4a8e33b8 Docker app, PostgreSQL16 and real compiled runner, synthetic data only. No production session or customer data used. Final aggregate and remaining original acceptance criteria are not complete.

## Users, tasks and success conditions

Owners/managers need to move from a concrete opportunity to a reviewed action and recorded result; network users must keep the selected business unambiguous. Superadmin demo tools have separate permissions. The journey landing pages should answer what the opportunity is, what to do first, and what will remain under manual approval. These are separate from the five primary performance journeys in `01-system-map.md`.

## Evidence matrix

| Flow / failure mechanism | Validation | Result / limits |
| --- | --- | --- |
| Public maps/influencer/partnership/content/automation opportunities | Three viewports; next action, approval note, measured contrast | Pass in latest114-case run; not every screen's accessibility audit |
| Registration → email verification → selected action | Real API/DB and synthetic verification fixture; five flows × three viewports | Fifteen pass; actual email delivery intentionally disabled |
| Authenticated Today/growth/influencers/partnerships/content/agents | Named controls, API denials, mobile hit targets and axe | Eighteen pass across three viewports after the causal attention-title contrast correction; not an all-pages accessibility certification |
| Web → Mini App → web continuity; retry after lost response | Signed synthetic Mini App fixture, real action versions/idempotency | Pass; no live Telegram account/provider operation |
| Business/network scope | Real owner/foreign network records, selected aggregate/location | Pass; negative stored-role backend tests separately cover viewer writes |
| Reviews/manual draft and finance import | Real stored review draft; preview → explicit apply → duplicate retry | Pass; no real review publication/CRM request |
| Complete five journey projections | Real API/domain records plus explicit completion fixtures | Pass for workflow projection. Map-worker/automation completion is injected by synthetic fixtures, not proof of actual parser/worker/provider execution |
| Approved compiled table → actual report/CSV |10real previews/5executions precede browser; approved version, real report/CSV, keyboard collapse/viewport bounds | **Three pass**, one perviewport. No row fabricated or assertion skipped; model generation/provider writes not exercised |
| External script unavailable/no analytics consent | Closed external browser proxy, explicit script interception | Pass; no live external integration validation |
| Uncertain social publication → receipt reconciliation | 19 UI tests and actual API/DB receipt/double-confirmation controls | All3viewports now pass after mobile layout correction; no real provider send. Final image/release remains separate |
| Month calendar → publication sheet → close → List | Normal pointer, clientWidth overflow bounds, Escape and focus restoration | All3viewports pass after reviewed20431224; part of120/120full run |

## UX-CALENDAR-03 and A11Y-CONTENT-04

The owner needs to inspect a publication, reconcile an already completed send,
then continue from the same card without another send or keyboard-navigation
reset. A393px mobile device acquired a762px layout because the calendar grid
child kept its intrinsic minimum width; nonwrapping navigation kept437px even
in List. Visual-viewport offsets made an ordinary sheet click hit the date
label although the elements did not physically overlap. Measured regression
fails with369px root overflow. Two existing utility classes constrain the grid
child and wrap navigation; no information is hidden or interaction forced.

After that correction, the new browser check reaches receipt details on all
viewports, but Escape leaves focus inactive. The controlled Sheet has no
SheetTrigger, so restoration must explicitly remember the actual activated
calendar/List/nearest button. The scoped correction focuses only a connected,
enabled saved node and clears it; URL/programmatic opens retain default
behavior. Browser assertions are unchanged, now pass across all3viewports,
and retain the original failure capture.

Viewports: desktop1440×1000, laptop1024×768, mobile393×852. Suite uses Russian locale, one browser worker, synthetic users and disabled provider/dispatch credentials. The browser proxy blocks non-loopback connections. Native runs use a Python egress guard; the later Docker application/PG/runner use internal networks. Native fixture subprocess preserves its guard and removes libpq overrides.

## Before and after

Current Docker run uses internal app/PG/runner networks instead of a backend Python hook; Python proof harness retains its egress guard. Fixed ingress proxy has a documented host-access network egress exception. Full4a8 browser result was **111passed3failed215.298s**, `raw/browser-4a8e33b8-full.json`. These were three new color-contrast failures, not the previous missing-fixture failures. The first source hypothesis incorrectly mapped the direct-child target to the nested workflow graph; its rebuilt5c1 rerun remained111/3. Trace inspection identified EmployeeWorkspaceSection title `Готовность процесса`; commit8ebec5ca corrected that caption. The clean rebuilt frontend then passed **114/114 in215.263s** on the same isolated backend. All failed captures are retained; approval rules and state were not changed by this contrast fix. The native result below is historical.

Baseline real-API suite:95passed19failed330.392s. Confirmed application problems were unstable journey URL/effect lifecycle and undersized influencer mobile targets; other failures included harness locale/copy/target drift. Those causes were not lumped into a single app defect.

Reviewed fixes:

- Journey effect/navigation lifecycle:22589aed; causal unit red2/7 → green11; late preparation/token response controls retained.
- Influencer hit areas:adae95d6; existing token-based40px targets, no unrelated redesign.
- Revoked selected business:98bd5ecf; private state resets/remounts on lost scope.
- Finance scope/input reset:f7357c63; stale preview cannot import into another selected business.

Earlier native full real-API run: **111passed3failed200.079s**, `raw/native-pg-real-api-browser-unset.json`. Backend b9a146aa; patched built frontend fromadae95d6, existing0b harness plus618native fixture guard. This was not the91797c74 security-patch browser release, nor a clean Docker runtime. The timing difference is not a performance improvement claim because hosts/runtime/test failures differ.

Initial native attempt36pass78fail153.249s is retained in `raw/native-pg-real-api-browser.json`. It exposed root's new helper regression: blank libpq service variables are not unset. Corrected through actual subprocess verification and rerun; those78 failures did not demonstrate broken pages.

## Falsified candidates and remaining work

UX-SVC-01, UX-CONTENT-01 and UX-OP-01 cross-business state-overwrite hypotheses were **NO_BUG_PROVEN**: actual DashboardLayout's keyed Outlet unmounts the old business page. A test reusing a page under new props would bypass the real route contract. This does not prove same-business races or uncertain external-send retries safe.

Still required for broader release closure: exact current immutable-image/compiled-runtime proof, large-data and controlled slow-network measurements beyond the tested states, broader same-business concurrency/provider uncertainty, and rehearsed partner demo. Current272native117 and historical120 already include social-publication receipt/reconciliation; that integration is not pending. Required critical-flow keyboard/focus/error/empty/slow contracts have scoped AC3PASS; this is not all-pages accessibility or production-ready sign-off.

## Authenticated IAB follow-up — 20 September

User-confirmed login enabled read-only navigation across Today, Progress,
Content and Agents; all rendered, and bounded captured error/warn logs were
empty. No settings, approvals, generation or external actions were submitted.
This is not a complete scenario or current-build certification.

Existing UX-LOCALE-07 remains visible on Today despite locally translated static
keys. The deployed revision/cache/runtime-language cause is not established.
Progress additionally exposes hardcoded Russian system copy in
ManagedCardGrowthPanel and its managed-growth page branch; current i18n tests
omit card_state, so that branch remains uncovered. User-authored titles and
business content are excluded. See raw/iab-authenticated-navigation-20260920.md.
