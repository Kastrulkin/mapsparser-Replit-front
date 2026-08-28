# Content editorial gate: red-to-green report

## Result

`FIX_PROVEN`

LocalOS accepted generic summaries in the master draft, accepted unsupported details in platform adaptations, and allowed approval without a current editorial review. Three focused tests reproduced those paths before production code changed.

## Root cause

- The content neuroslop check was a finite phrase list rather than a shared editorial contract.
- Platform adaptation only normalized length, hashtags, and technical markers.
- Approval and queue flows checked text presence and human approval, but did not recompute editorial quality.

## Fix

- Added `content-editorial-v3`, shared by master generation and platform variants.
- Added positive natural-language constraints to both generation prompts.
- Added checks for generic summaries, abstract benefits, unsupported details, and unsupported business-wide habits.
- Platform variants that fail receive `variant_status=failed` and are not prepared as ready copy.
- Manual edits are reviewed immediately.
- Approval and queue recompute quality from the current text.
- The Content UI shows `Нужно переписать` and the concrete reasons.
- Existing unpublished posts are reviewed read-only when the plan is opened. Published posts remain unchanged.

## Evidence

- Reproducer before fix: `3 failed`.
- Same tests after fix: `3 passed`.
- Backend regression suites: `221 passed`.
- Content page test: `12 passed`.
- Production frontend build: passed.

## Limits

The implementation is complete and verified locally. It has not been deployed or used to rewrite production data in this change.
