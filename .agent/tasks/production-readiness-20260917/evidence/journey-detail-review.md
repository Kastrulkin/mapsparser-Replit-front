# Journey detail-load — independent source review

Reviewed the UX-JOURNEY-DETAIL-LOAD-09 implementation against parent
`d72475e3`; no tests were executed in this review.

## Scope and source verdict

**PASS, bounded source review.** `JourneyWorkspaceFocus` keeps the workspace
children outside the keyed `JourneyFocusPanel`. Its panel key is the complete
business/action query intent, so a changed URL removes the old card, loading
state and error synchronously without remounting the destination workspace.

The panel owns a per-mount layout-effect lifetime object and a per-load
generation. Detail success, failure and finalization mutate state only for the
current generation. A matching same-intent retry retains the existing card and
therefore the card's local draft/retry state; 401, 403 and 404 for the current
request deliberately clear a cached action, while transient failures do not.

The parent one-shot handoff seed is keyed by the target business/action intent.
It lets an authoritative current command result display the next action while
the canonical GET refreshes it, then is cleared after the keyed panel has
initialized so a later revisit cannot reuse it. `continueWith` checks the
latest route intent before URL replacement and clones the latest search
parameters before replacing only `journey_action`; non-action parameters are
preserved. A panel lifetime check and incremented generation fence its command
handoff.

No payload, command, approval, backend, API, schema, provider, or child
workspace behavior is broadened by this source change.

## Limits pending final evidence

This is a static/source conclusion only. It does not prove React Router
concurrent scheduling beyond the scoped regression harness, real network/API
ordering, native browser/mobile/RTL behavior, LanguageProvider loading,
backend/DB/provider behavior, or deployment. Final test, type/lint, build,
integrity, manifest, and full-frontend captures are required before package
closure. Parent/detail-load races outside this focused Journey panel remain
separate.

## Final bounded evidence closure

**PASS for UX-JOURNEY-DETAIL-LOAD-09; not a whole-readiness or production
verdict.** The final full frontend capture reports 791 tests across 137 files,
exit 0, 319678.171 ms, with no timeout or capture truncation. The focused
capture reports 104 tests in the five actually matched files, exit 0,
18960.526 ms; its command listed two nonmatching historical names, so this
review does not inflate it to seven files. The Focus module itself has 20
cases, including stale A/B result/error/loading ordering, same-intent overlap
and retry, access-denial versus transient preservation, retained card and
child drafts, StrictMode, stale command navigation, one-shot handoff/revisit,
and preservation of unrelated query parameters.

Both TypeScript projects and lint pass in 49518.454 ms with the pre-existing
`auth_new.ts:115` warning only. The isolated build exits 0 in 14375.571 ms;
its asset-table stdout is capture-truncated, but the result and stderr are
complete. The independent 199-JS integrity check exits 0 in 287.790 ms. All
14 current manifest inputs match. The full-run stderr has the same SHA-256 as
the prior scope full run and is retained known negative-fixture/jsdom output,
not a new test failure.

Remaining limits are unchanged: mocked/jsdom scope only; no proof of other
parent/detail-loader races, real Router scheduler edge cases beyond the
regressions, LanguageProvider loading/remount, native browser/mobile/RTL,
backend/API/provider/DB or deployment behavior. No production action is
authorized or implied.
