# UX-AGENT-SCHEDULE-01 — keep settings aligned with the selected version

Parent: `bd487501dd22733f92fa5cce80766ead60a554ec`. P2 before demo.
Screen job: an owner reviews one agent's schedule, optionally edits it and
explicitly saves the intended next version without changing another agent.

## Live observation and causal contract

The authenticated read-only browser pass observed Scenario showing 18:00 and
Settings showing 09:00 for the same selected agent and timezone. No live field
edit, save, run, activation or publication was performed. See the separate
`authenticated-browser-readonly-20260921.md`; its deployed revision is unknown.

Scenario reads `execution_contract.candidate || active` in `agents/employee.tsx`.
The workspace previously hydrated its settings only from legacy
`metadata_json.custom_process.schedule`, leaving the default 09:00 when absent.
Backend `_agent_schedule_status` prefers the selected version's schedule and
only falls back to metadata for an empty schedule. Both save endpoints create
a new candidate and explicitly leave the active version unchanged. The defect
can therefore place an unintended time in a later approved version; it is not
evidence of an immediate active-schedule overwrite.

## Local implementation

Only `AgentBlueprintsWorkspace.tsx` changes runtime behavior. Settings choose the
same candidate-or-active version; a candidate with no schedule does not borrow
another version's schedule. Legacy metadata remains the compatibility fallback.
The selected business/blueprint must match; matching detail identity is required
before using the version contract. Legacy values can appear while details load.
After matching details have arrived, stale details for another selection cannot
replace the schedule. Changing scope clears old form state.

Time, timezone and execution-mode edits have separate dirty markers/revisions.
Shared form setters preserve unsaved values during same-selection refreshes.
Successful saves clear only markers from the same hydration object and unchanged
field revision, retaining newer edits and avoiding A→B→A identity collisions.
The save payloads, API routes, approval and activation boundaries are unchanged.

## Tests and evidence provenance

The tests mount the actual workspace state and `AgentExecutionModePanel`, with a
small mocked view harness. Auth/API/run hooks are stubbed, global fetch throws,
and every case asserts no API POST. They are not a complete browser-rendered
workspace or a server API test. The private Vitest config disables `.env` reads.

- Initial three-case RED: 10108.876ms, three failures. Root found latent no-op
  input handlers in the harness; the third case failed before reaching them.
  This capture is retained, not the authoritative final regression.
- Corrected three-case RED: 9492.254ms, three failures, test hash `e158d22c…`.
  Later fixture business IDs and adjacent cases changed that test file; this
  earlier capture is not relabeled as proof for final test bytes.
- First five-case immutable-parent/current pair: 12637.013ms / 5687.621ms,
  five failures / five passes, test hash `c23d257b…`. Root then strengthened the
  stale-response test to wait for the wrong detail ID to actually arrive before
  asserting the selected time. Both earlier captures remain intact.
- Authoritative `agent-schedule-verified-baseline-20260921.json`: five failures,
  13439.965ms. The Vite load hook injects only the immutable parent workspace,
  verifies its SHA-256, prints the injected source and final test hashes, and
  leaves working source untouched. No source reversal or capture overwrite.
- Same final tests, `agent-schedule-verified-green-20260921.json`: five passes
  in 4.21s, 5654.975ms captured. Coverage: candidate beats stale metadata;
  active-only fallback; deferred legacy-to-candidate hydration; stale A response
  after B is selected; unsaved time survives a completed matching refresh.
- `agent-schedule-quality-20260921.json`: both TypeScript projects and full
  frontend ESLint pass in 54259.885ms, with one existing `auth_new.ts:115` any
  warning. This is not warning-free lint.
- `agent-schedule-build-20260921.json`: fresh private build passes in
  19792.826ms. Rollup dependency annotation warnings and the fresh external
  output-directory notice are retained. Nothing was deployed.

Full unit suite:814tests/138files pass,344.09s Vitest,345434.781ms captured.
Stderr retains fixture warnings and simulated-error diagnostics; not a clean
production console claim. Asset-integrity check verifies199reachable JS files,
204.939ms. All ten captures have no timeout or output truncation. Final manifest
binds16source/harness/dependency hashes and capture digests. Independent bounded
review accepted exact workspace `a2e7503d…`, test `fe802fcb…` and baseline config.
Review explicitly withdrew an earlier per-field active-fallback suggestion:
the selected version object, not a blend of two versions, is the contract.

## Limits

Pending-save, explicit business switching, create-wizard edits and empty/partial
contract matrices are not all automated by these five cases. The shared setters
and completion guards require source review; no broad asynchronous-workspace
certification is claimed. Existing detail-loader races outside schedule hydration
are not fixed here. No production schedule is changed and no new-build browser
pass is claimed. Broader native aggregate/restore, image, demo/CI, secret lifecycle
and whole-readiness FAIL remain unchanged; nine unrelated dirty paths are kept.
