# Journey detail intent/loading — local verification

Parentd72475e3, UX-JOURNEY-DETAIL-LOAD-09. Previous goal turn made progress:
action form/request lifetime locally committed,771frontend/136files pass and
independent bounded review closed. Whole-project production-readiness staysFAIL.

Task: follow the action selected in the URL without allowing an older detail
request to replace it, erase its loading/error state or expose a wrong clickable
card. Main root reread original1016-line objective through EOF, bug-reproducer,
shared execution contract/discovery playbook and DESIGN. Current nine foreign
paths unchanged; no own residue at start. Scope is local frontend only.

Current Focus is stable across query-only navigation; it retains previous action
while loading and updates action/error/loading without request sequencing. The
prior keyed card fix cannot reject its parent's stale detail response. Dashboard
business switches remount Outlet; do not infer a cross-tenant leak or mutation.

Root initial causal RED3fail/7pass across5newrouter cases+5existingcard cases,
6.26s/capture8465.478ms, exit1/no timeout/truncation. B is replaced by oldA after
ordered deferred responses; oldA error leaks into pendingB; loadedA remains
visible/clickable during B load. Query removal and current transient Retry are
positive controls. First failure precedes stale-telemetry assertion, second
precedes loading assertion; do not claim those were separately observed in RED.
No actual backend mutation/provider effect. Mocked real router and real card.

Root owns Focus source/evidence/execution; worker initially owned new Focus tests.
Independent design review recommends keyed focus-only panel plus per-request
lifetime/generation; children must remain outside the key. Same-intent retries
retain drafts; successful nextAction handoff should remain immediate, preserving
latest unrelated URL params. Root reviewed the expanded harness before execution:
the first overlap draft tried Retry while no error existed. It was corrected to
two supported save_draft completions with absent next_action, each causing a
detail reload. No original failing assertion was weakened or fixture failure
counted as a product bug. Expanded RED ran on unchanged source:8failed/11passed,
19tests in6.53s/capture8757.466ms, no timeout/truncation. Additional causal results:
older same-intent reload overwrites newer;401/403/404 leaves cached card visible;
late current command rolls back unrelated query foo to its old value. Immediate
next-action display already passed and must remain supported.

Implementation changes only JourneyWorkspaceFocus.tsx. A keyed focus panel owns
action/loading/error and layout lifetime+request generation; the workspace
children remain stable siblings. Older then/catch/finally cannot mutate current
intent. Current401/403/404 removes focus, transient500/null retains confirmed
same-intent action and local fields.404 means not addressable (including flag/
business access/action absence), not proof of deletion. Existing backend error
contract was independently inspected; no API/backend/schema change.

Command handoff invalidates pending GET and seeds the new panel immediately.
Parent clears that one-shot seed after the new intent commits, preventing later
reuse. Latest committed route ref preserves unrelated params; source-key and
panel/card lifetimes reject departed callbacks. No cancellation or rollback of
already-started commands is claimed. No broad architecture/Telegram refactor.

Root added three adjacent tests after worker freeze: StrictMode replay, departed
command navigation, and seeded-B transient failure/edit/revisit. Retry assertions
also require error disappearance and exact third GET. Final Focus suite20cases
includes independent child state across action/removal and real-card edited-field
retention, not just a static child label. Targeted104tests/5actual files pass
16.72s/capture18960.526ms with empty stderr and no timeout/truncation. The selection
command included two nonmatching stale Telegram paths; these provide NO coverage.
Actual files are Focus, base/scope/i18n Card and Today. The full suite will cover
actual TelegramControlPage/Progress specs. Fourteen source/test/config/guard
inputs frozen after targeted pass, manifest35.3ms. Quality passes49518.454ms:
app/node TypeScript and full ESLint, one existing auth_new.ts115 any warning.
Build succeeds12.72s/capture14375.571ms into a new temporary dist (below), with
existing Yandex PURE/external-outDir warnings. Build stdout is truncated at the
30000-character capture budget: exit0 and final build summary are retained, but
do not describe it as a complete per-asset log. stderr is complete. Integrity
capture287.79ms passes all199reachable JS files, no truncation, plus a nonfatal
Darwin temp-dir fallback warning. Entryindex-CcDNxgy1.js/CSSindex-BM6vOqzw.css.
Artifact:/private/tmp/localos-journey-detail-build-20260921.ScKt6f/dist.
Frozen full frontend:791tests/137files pass317.37s/capture319678.171ms, exit0,
no timeout/truncation. All14manifest hashes match afterward. Full stderr equals
the prior journey-scope-full capture byte-for-byte (14259characters): known jsdom
limitations and intentional negative auth/network/error-boundary diagnostics.
No audit test/build job remains live. Local bounded FIX_PROVEN; independent final
closure is in journey-detail-review.md. This is not whole-project readiness.

Precommit1408.2ms passes14hash checks, staged diff-check, Gitleaks211907bytes/no
findings and unchanged original overallFAIL/onlyAC10PASS. Nonfatal Darwin temp
fallback warnings retained. Root stages only this24file source/test/evidence/docs
package; nine foreign paths excluded. Local commit only, no push/deployment.

All test API/command calls are mocked. env-i strips inherited configuration;
Node22 loads the retained process-local no-egress guard chain, Vite envDir:false.
This is not an OS-level isolation certificate or real API/browser proof.

Latest disk6,788,632KiB (~6.47GiB), below10GiB image floor. No native DB, Docker,
cleanup, push/deploy, production/provider/send action. Aggregate/restore
preparation denials and prior unsafe-reset INCONCLUSIVE effects persist.
