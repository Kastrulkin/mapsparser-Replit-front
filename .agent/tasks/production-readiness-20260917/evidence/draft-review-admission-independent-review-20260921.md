# Independent draft-review admission fix review — 2026-09-21

## Scope and method

Read-only static review of the current five-file draft-approval admission patch. No source files were edited and no tests, build, browser, network, database, Docker, or scripts were run. The review checks the existing UI completeness contract, generic approvals, rejection availability, loading behavior, and prop-driven rerenders. It does not re-review backend freshness validation.

## Verdict

`NO_BUG_PROVEN` for the reviewed patch: no reachable regression was identified in the changed UI behavior.

The shared predicate is drafts-only and preserves the exact pre-existing snapshot condition used by the warning: version 1, non-empty `items`, and a non-blank `review_text` on every item. Consequently, the warning and the approve control now derive from one condition instead of drifting independently.

## Contract checks

- Incomplete `drafts` snapshots leave Approve visible but disabled in both manager detail and employee views; Reject remains available.
- Valid `drafts` snapshots still allow Approve unless an action is loading.
- A non-draft/generic approval is not captured by the draft predicate and retains its existing approval path.
- Both control states are computed from current props during render, so a stale -> valid -> stale approval rerender updates the affordance without local state retention.
- While an action is loading, both actions remain disabled as before; the stale-snapshot condition does not alter that shared loading guard.

## Test coverage inspected (not executed)

`draftApprovalSnapshot.test.tsx` covers the incomplete shapes (missing version, non-array or empty items, blank text, and invalid item after a valid item) for both screens. It asserts the disabled approve/no approval callback boundary, enabled reject/callback boundary, valid snapshot approval, stale/valid/stale rerender transitions, loading behavior, and a generic custom approval that remains approvable. This is an appropriate deterministic regression suite for the UI admission decision.

## Intentional boundary

The UI predicate intentionally does not add recipient/count validation or replicate backend freshness checks. Backend validation remains the authority for stale or otherwise invalid submitted approval payloads; this change only aligns the existing frontend warning with the existing frontend control state.

## Reviewed implementation and test paths

- `frontend/src/pages/dashboard/agents/runs.logic.ts`
- `frontend/src/pages/dashboard/agents/runs.tsx`
- `frontend/src/pages/dashboard/agents/detail.tsx`
- `frontend/src/pages/dashboard/agents/employee.tsx`
- `frontend/src/pages/dashboard/agents/draftApprovalSnapshot.test.tsx`

## Limitations

This is static source review only. It does not establish that the suite passes in the local/runtime environment, exercise API failures, or replace backend approval freshness validation.
