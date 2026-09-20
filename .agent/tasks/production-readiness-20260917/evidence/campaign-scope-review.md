# Independent bounded campaign-scope review

Parent: 03ef38f6. Reviewer: draft_approval_regression, read-only actual source
inspection; transcribed by root. No reviewer executions or source modifications.

Source verdict: PASS for UX-CAMPAIGN-SCOPE-02, not whole-project readiness.

- Exact workstream/business/segment key remounts private state synchronously,
  while ordinary unchanged-key renders preserve the editor.
- Layout effect creates a distinct token and cleanup invalidates that exact
  object. StrictMode cannot re-enable its first setup's requests.
- All loader/action awaits, rejection paths and busy finalizers are guarded.
  Follow-up loaders, selection updates and onChanged callbacks are rechecked.
- A→B→A receives a new lifetime; immediate old-card removal, old save, unmount,
  recommendation, same-key preservation and StrictMode tests match the boundary.
- The production drawer supplies all three keyed inputs. No endpoint/payload,
  backend consent, provider send or approval policy changes.

Residuals: requests already started are not cancelled; competing requests in
one unchanged lifetime are not ordered by this fence. The separately traced
unsaved-preview/saved-campaign consent mismatch is not part of this correction.
Bounded evidence reconciliation: PASS. Reviewer read actual RED/intermediate/
final/backend/quality/build/integrity captures and matched every nonblank
manifest entry to current files. Final targeted result is 26/26, not the older
24-test run. RED assertion limitations and no-native/live-effect claims are
accurate. Final full-capture reconciliation is also PASS for this package:
709tests/133files,330.49s/capture331940.084ms, exit0, no timeout/truncation.
Reviewer checked the full capture and again matched all nine hashes. Stderr
contains documented jsdom limitations and deliberate negative network/auth/
error-boundary fixture diagnostics, not a reported unhandled/test failure.
No native browser/API/DB, deployment or whole-goal verdict is implied.
