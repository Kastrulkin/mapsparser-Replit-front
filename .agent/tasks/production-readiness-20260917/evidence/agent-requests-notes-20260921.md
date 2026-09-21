# Selected-agent request integrity — 21 September 2026

Parent: `b9cb7dea2b3fcf651a976e64a6e986b306bf9ca9`.
Finding: UX-AGENT-REQUEST-SCOPE-01, P1 / before demo and production.

## Contract and reproduced effect

Screen job: the owner reviews and decides on the result of the employee currently
selected in the same business. DESIGN.md requires explicit request/state scope;
the real view renders the selected employee beside workspace details and derives
its result-review action from that data. The server authorizes each agent, but
does not know which other agent the browser presently displays.

The selected-detail loader commits every response without request ordering or
selection validation. Clearing details in the selection effect does not cancel
an earlier request. The review loader has the same race. The previous schedule
fix protected only the schedule fields, not history, results or approvals.

The baseline regression mounts the real workspace with a small view
harness and a fully mocked API. A detail request is deferred; B is selected and
its result/approval loads while the separate run GET remains pending. Resolving
A then clicking the harness action invokes the real `decideApproval` handler:
the mock records A's run/approval URL instead of B's. No real POST, provider or
production mutation occurs. This establishes wrong-agent UI/action routing,
not a backend authorization bypass or observed cross-tenant disclosure.
DashboardLayout keys/remounts its Outlet on business/control-scope changes.

The final ten cases also cover a stale error, same-agent refresh order,
filter order, two malformed response identities, review order, a legitimate
select-plus-load in the same event, reopening the already-selected employee,
and derived selection after the registry removes the selected employee.
Malformed identity cases are robustness
checks, not proof that the production API emits another tenant's data.
Filter-order, same-event selection and reopening the selected employee already
pass the baseline; they are compatibility checks, not counted among the seven
causal failures. Independent
test review accepted the deferred assertions and actual approval-handler route.

## Evidence provenance

- `agent-requests-red-20260921.json`:90s timeout, no test result. The initial
  test context returned a fresh currentBusiness object on every render, looping
  the existing configuration effect. This is a harness defect, not product RED.
  Its orphan Vitest worker PID59307 was verified in our completed pane process
  group59149 and terminated with SIGTERM; other processes were untouched.
- `agent-requests-causal-red-20260921.json`:11738.462ms,5failed/3passed plus
  two harness errors. The harness called an unexposed review function; that case
  was corrected to use the actual automatic review-on-selection path.
- `agent-requests-verified-red-20260921.json`:12890.634ms,6assertion failures/
  2passes, no unhandled errors, timeout or truncation. This is an intermediate
  eight-case pre-fix result. Test SHA-256 is
  `9a758fc2009f77e7a6590a4372f6968c2a7dc6b1108f52c15647d0bce5733cc0`;
  workspace SHA-256 is
  `a2e7503d70b8d2b6e9250f09eb4ac68eb85dae38aff9231bf74883eab97fad01`.
- `agent-requests-final-baseline-20260921.json`: nine cases on immutable
  parent,6fail/3pass,7037.289ms. The ninth case protects same-selection no-op
  behavior caught during implementation; the intermediate current pair has
  14passes including five schedule tests (`agent-requests-green`,10074.145ms).
- Review then found that registry refresh can remove A and derive selection B
  without calling the explicit setter, leaving A's review temporarily visible.
  The effect now clears review on this derived transition; the tenth test
  requires an empty review until B's deferred review resolves.
- Authoritative final same-test baseline is
  `agent-requests-review-baseline-20260921.json`:7assertion failures/3passes,
  5926.484ms. Final test SHA-256:
  `20e70b115884b4adadc1dc65b6ace8dc6adf097185b1f33c468d777d7f634393`.
  The immutable-parent load hook logs and checks source/test provenance without
  reversing working files. No unhandled errors, timeout or truncation.
- Authoritative focused current proof is
  `agent-requests-review-green-20260921.json`: all15cases pass,7686.926ms,
  including ten request cases and five schedule cases. The controlled stale
  rejection logs `Error: old A failure`; it is not suppressed or unhandled.

The existing schedule regression is deliberately strengthened: after draining
the old deferred response, both loaded detail identity and time must remain B.
Its former assertion that A details appear was evidence of this separate bug,
not a desired behavior to preserve.

## Implemented boundary and independent review

Only workspace selected-detail/review state and its selection entrypoints
change. A synchronous business/employee ref supports select-plus-load in one
event; selecting the same employee is a no-op. Independent per-key request
revisions reject superseded responses; a business-generation counter prevents
old responses matching reused counters after a scope reset. Detail payload
identity must match the requested business and employee before cache admission;
primary detail/error/review state also requires the current selection.
Derived selection clears old review, and business changes clear detail cache.
The run-tracking setter adapter retains its functional-update type contract.
Create/template/deep-link callers still use the existing actions and payloads.

Frozen workspace SHA-256:
`7c213391643036744d5907080b9cdaf05ab34814ad87e78f7d97a0e5a1862ed3`.
Independent read-only review accepted final source and causal/compatibility
tests after the derived-selection correction. Earlier intermediate workspace
`5dd92043…` had14green cases and passed quality checks, but that result is not
relabeled as verification of the final source.

Final full frontend824tests/139files passes321.36s (322609.470ms capture).
Both TypeScript projects and full ESLint pass with one pre-existing warning;
copy guard passes for the page wrapper only. Fresh build14622.934ms and
199-JS integrity205.322ms pass. Final independent evidence review ACCEPT:
prior full-suite stderr categories/counts are unchanged; sole new heading is
the intentional caught late-A rejection. Build retains four third-party PURE
annotation warnings and the expected private outDir warning.
Nineteen source/config/dependency hashes and twelve immutable captures are
bound in the accompanying manifest and COMMANDS checkpoint. No claim
is made about list-refresh ordering, connection/source reads, mutation completion
races, comprehensive live-browser behavior, native DB or production readiness.
Those boundaries remain separate from the selected details/review correction.
