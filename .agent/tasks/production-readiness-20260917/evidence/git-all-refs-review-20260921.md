# Frozen local Git refs audit review — 21 September 2026

## Scope and method

Independent evidence-only review of the `git-all-refs-20260921` package and
`support/git_refs_inventory_20260921.cjs`. I inspected only the inventory,
manifest/validation, redacted metadata projections, and priority
verification/triage records. I did not open either raw redacted scanner report,
private copied blob contents, or secret values; nor did I execute a command,
scanner, test, Git operation, network action, or application/runtime check.

## Bounded result

**ACCEPTED AS PARTIAL, REDACTED LOCAL-REFS EVIDENCE — NOT AS COMPLETE SECRET
COVERAGE.**

- The verified inventory is internally linked: 89 local refs, 35 commit tips
  (including HEAD, stash and locally cached remote refs), 3,117 reachable
  commits, 13 tree refs / 11 unique roots, and 938 explicit tree-only blobs
  (123,138,155 bytes). Input validation records manifest and source-script
  digests, and compares the scanner binary/config plus every raw blob's
  SHA-1/SHA-256 and private permissions. The initial inventory stop (`exit -15`, 98,253.167 ms) is retained as
  neither timeout nor success; the fresh verified inventory exits 0 in
  56,325.694 ms.
- The earlier preparation concerns are correctly withdrawn. The tracked
  manifest is metadata-only and exclusive-created; a nonrecursive snapshot
  directory creation rejects pre-existence before blob writes. The revised
  helper disables replacement objects, system/global Git configuration and
  prompts, while in-process raw Git-blob hashing replaces `hash-object`; no
  Git filters are invoked for that validation.
- Two scans intentionally exit 1 because they report findings, not because the
  scanner crashed: history has 711 reported findings in 399,800.426 ms and
  tree-only blobs have 42 in 15,844.436 ms. The metadata projection ties each
  history row to the frozen commit set or each tree row to an explicitly
  materialized blob, and records all secret fields as redacted.
- Priority verification is accurately narrow: 20 locations are classified as
  two historical privileged `service_role` JWT locations, one historical
  Wordstat opaque-token location, and 17 historical public-anon JWT locations.
  It establishes only storage context and decoded shape/role. Signature,
  validity, exploitability, rotation, revocation, and provider reachability
  remain untested.

## Unresolved coverage and remaining work

The package must retain **UNRESOLVED** coverage reconciliation: the frozen graph
contains 3,117 selected commits but the history scanner accounts for 3,095.
Raw-diff and numstat metadata account for empty/deletion/binary cases only in
part and do not fully explain that 22-commit difference. Consequently, neither
the history scan nor the combined history/tree result can be called complete
all-selected-commit coverage.

After the 20 priority locations, 733 reported findings remain unreviewed
(711 history + 42 tree-only − 20 priority). The redacted metadata is therefore
an inventory and prioritization aid, not a clean-scan result or a finding-level
adjudication of the remaining rows.

## Scope limits

This covers only locally available frozen refs and separately copied direct
tree-ref blobs. It excludes remote-only refs, reflog-only/dangling/unreachable
or pruned objects, dirty/untracked/ignored non-Git files, resolved LFS content,
nested archives, semantic binary inspection, images, runtime logs, deployment
configuration, and all credential/provider validation or revocation work.

No AC6 or overall-production-readiness PASS follows. The historical verdict,
original FAIL criteria, nine foreign-path exclusion, denied native/restore
preparation, and no-DB/Docker/network/push/deploy boundary remain unchanged.

## Latest ledger reconciliation

**ACCEPTED.** The latest package notes, readiness checkpoint, and task evidence
use the same totals: 3,117 selected graph commits versus 3,095 scanner-reported
history commits; 711 history and 42 tree findings; 20 priority history locations
classified; and 691 remaining history plus 42 tree findings = 733 unreviewed.
They also consistently retain the partial explanatory diagnostics (3,112
nonempty raw diffs and 3,085/3,087 numstat additions) without presenting them
as a solution to the 22-commit discrepancy. No numeric or status inconsistency
was found in those latest summaries.
