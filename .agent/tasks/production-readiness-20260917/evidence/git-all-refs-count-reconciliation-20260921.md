# Frozen all-refs commit-count reconciliation — 2026-09-21

## Scope and result

This is a read-only reconciliation of the frozen all-local-refs capture, not a
second scanner invocation.  It does not expose finding values, patch text, or
any secret-bearing history lines.

The two numbers measure different things:

| Measure | Count | Provenance |
| --- | ---: | --- |
| Reachable commits in the frozen ref graph | 3,117 | `git-all-refs-manifest-20260921.json` (`reachableCommitCount`) |
| Unique commits from the frozen 35 `commitTips` using `git rev-list --stdin --count` | 3,117 | read-only reconciliation, 2026-09-21 |
| Unique commit headers from an equivalent frozen `git log --full-history --no-ext-diff --no-textconv -m --root` walk | 3,117 | read-only reconciliation, 2026-09-21 |
| Gitleaks history run's reported `commits scanned` | 3,095 | `git-all-refs-history-20260921.json` (redacted execution capture) |

Therefore, the 22-count difference is **not evidence that the frozen ref list
or Git graph omitted 22 commits**.  The manifest's frozen 35 roots and the
Git walk agree exactly on 3,117.

## Counter semantics established from primary source

Gitleaks v8.30.1 records a commit in its `commitMap` only when its detector is
given a fragment carrying that commit SHA; it then logs the map size as
`commits scanned`.  The same source immediately warns that this number can be
smaller than expected because of commits with no additions.

- Detector counter and warning: <https://raw.githubusercontent.com/gitleaks/gitleaks/v8.30.1/detect/detect.go>
  (lines 192–245 in the fetched v8.30.1 source).
- Git source skips deletion-only diff files and non-archive binary files, and
  yields text fragments from additions: <https://raw.githubusercontent.com/gitleaks/gitleaks/v8.30.1/sources/git.go>
  (lines 280–405 in the fetched v8.30.1 source).
- With supplied log options, Gitleaks builds `git log -p -U0` and appends those
  options: <https://raw.githubusercontent.com/gitleaks/gitleaks/v8.30.1/sources/git.go>
  (lines 66–116 in the fetched v8.30.1 source).

Thus, 3,095 is a count of unique commits that reached Gitleaks fragment
processing, not a reachability/cardinality assertion.  The history capture did
not time out and has an expected nonzero scanner exit for findings; it must not
be represented as a clean pass.

## Existing local metadata cross-checks

The pre-existing, value-free aggregate captures support the distinction but do
not fully decompose the 22 commits:

| Capture | Safe aggregate result |
| --- | --- |
| `git-all-refs-patch-coverage-20260921.json` | 3,117 Git-log commits; 3,112 with a raw diff; 5 empty-diff commits. |
| `git-all-refs-addition-coverage-20260921.json` | Depending on rename treatment, 3,085 or 3,087 commits with positive text additions; 30–32 without them. |

These aggregates are intentionally not the Gitleaks parser's per-fragment
decision record.  In particular, a raw-diff, mode/rename, deletion, binary, or
empty-text-fragment case can affect the parser counter differently from a
`--numstat` aggregate.

## Exact unresolved boundary

The exact membership of the 22 commits cannot be proven from the retained
aggregate captures alone.  Establishing it would require a new per-commit
metadata projection from the exact Gitleaks diff-parser decision stream (or a
new equivalent instrumented scan).  Neither was performed here: this task
prohibited rerunning the whole scan and patch/history-content extraction.

Accordingly, the defensible conclusion is limited to: the 3,095/3,117
difference is an expected Gitleaks fragment-counter-versus-reachability metric
difference, while its exact 22-member decomposition remains unproven.  It is
not a basis to weaken the retained historical-finding verdict or to claim that
all history is clean.
