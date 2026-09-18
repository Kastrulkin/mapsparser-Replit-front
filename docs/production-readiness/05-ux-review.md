# UX and browser verification — working evidence

Scope: existing LocalOS task flows, not a redesign. Latest checkpoint17September2026, local native PostgreSQL15 + real Flask API + built frontend. No production session or customer data used. This report is incomplete until the compiled-runner path and remaining original acceptance criteria are verified.

## Users, tasks and success conditions

Owners/managers need to move from a concrete opportunity to a reviewed action and recorded result; network users must keep the selected business unambiguous. Superadmin demo tools have separate permissions. The journey landing pages should answer what the opportunity is, what to do first, and what will remain under manual approval. These are separate from the five primary performance journeys in `01-system-map.md`.

## Evidence matrix

| Flow / failure mechanism | Validation | Result / limits |
| --- | --- | --- |
| Public maps/influencer/partnership/content/automation opportunities | Three viewports; next action, approval note, measured contrast | Pass in latest114-case run; not every screen's accessibility audit |
| Registration → email verification → selected action | Real API/DB and synthetic verification fixture; five flows × three viewports | Fifteen pass; actual email delivery intentionally disabled |
| Authenticated Today/growth/influencers/partnerships/content/agents | Named controls, API denials, mobile hit targets | Eighteen pass; not all interactions on every page |
| Web → Mini App → web continuity; retry after lost response | Signed synthetic Mini App fixture, real action versions/idempotency | Pass; no live Telegram account/provider operation |
| Business/network scope | Real owner/foreign network records, selected aggregate/location | Pass; negative stored-role backend tests separately cover viewer writes |
| Reviews/manual draft and finance import | Real stored review draft; preview → explicit apply → duplicate retry | Pass; no real review publication/CRM request |
| Complete five journey projections | Real API/domain records plus explicit completion fixtures | Pass for workflow projection. Map-worker/automation completion is injected by synthetic fixtures, not proof of actual parser/worker/provider execution |
| Approved compiled table → actual report/CSV | Test requires an approved version and real completed runner report | **Three fail** (one perviewport): missing actual compiled runner fixture. No row fabricated or assertion skipped |
| External script unavailable/no analytics consent | Closed external browser proxy, explicit script interception | Pass; no live external integration validation |

Viewports: desktop1440×1000, laptop1024×768, mobile393×852. Suite uses Russian locale, one browser worker, synthetic users, disabled provider/dispatch credentials and a backend Python egress guard. The browser proxy blocks non-loopback connections. Native fixture subprocess now preserves its guard and removes libpq overrides.

## Before and after

Baseline real-API suite:95passed19failed330.392s. Confirmed application problems were unstable journey URL/effect lifecycle and undersized influencer mobile targets; other failures included harness locale/copy/target drift. Those causes were not lumped into a single app defect.

Reviewed fixes:

- Journey effect/navigation lifecycle:22589aed; causal unit red2/7 → green11; late preparation/token response controls retained.
- Influencer hit areas:adae95d6; existing token-based40px targets, no unrelated redesign.
- Revoked selected business:98bd5ecf; private state resets/remounts on lost scope.
- Finance scope/input reset:f7357c63; stale preview cannot import into another selected business.

Latest full real-API run: **111passed3failed200.079s**, `raw/native-pg-real-api-browser-unset.json`. Backend b9a146aa; patched built frontend fromadae95d6, existing0b harness plus618native fixture guard. This is not the91797c74 security-patch browser release, nor a clean Docker runtime. The timing difference is not a performance improvement claim because hosts/runtime/test failures differ.

Initial native attempt36pass78fail153.249s is retained in `raw/native-pg-real-api-browser.json`. It exposed root's new helper regression: blank libpq service variables are not unset. Corrected through actual subprocess verification and rerun; those78 failures did not demonstrate broken pages.

## Falsified candidates and remaining work

UX-SVC-01, UX-CONTENT-01 and UX-OP-01 cross-business state-overwrite hypotheses were **NO_BUG_PROVEN**: actual DashboardLayout's keyed Outlet unmounts the old business page. A test reusing a page under new props would bypass the real route contract. This does not prove same-business races or uncertain external-send retries safe.

Still required: real compiled runner/profile; exact final release/browser aggregate; broader keyboard/focus/error/loading/large-data coverage; controlled slow-network measurements; deterministic same-business concurrency/provider uncertainty; rehearsed partner demo. No all-pages/accessibility or production-ready sign-off.
