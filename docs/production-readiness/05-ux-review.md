# UX and browser verification — working evidence

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

Still required: exact final release/browser aggregate after the pending social-publication package; broader keyboard/focus/error/loading/large-data coverage; controlled slow-network measurements; deterministic same-business concurrency/provider uncertainty; rehearsed partner demo. The real compiled runner/profile gate passed at the checkpoint above. No all-pages/accessibility or production-ready sign-off.
