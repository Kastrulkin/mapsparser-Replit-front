# Frozen local Git refs: secret audit — 21 September 2026

Parent `7cf0cd24a8eec07be722084e467c8292b4f765ca` on
`codex/production-readiness-20260917`. The original objective was reread through
EOF. The preceding goal turn was progress: the Git onboarding correction was
committed, not merely proposed. This package addresses the distinct Git-history
coverage gap; it does not repeat the completed frontend/source review.

## Frozen inputs and boundaries

The metadata-only `git-all-refs-manifest-20260921.json` records 89 local refs,
35 unique commit tips including HEAD/stash/local cached remote refs, 3,117
reachable commits and the sorted commit-set digest. The repository is not shallow.
It also records 13 direct tree refs / 11 unique roots, plus 938 blob objects
(123,138,155 bytes) not reachable from those commit tips. Each extra blob was
copied into a fresh private directory under its object ID, never its original
path, and checked against the raw Git blob-header SHA-1. No historical symlink
was followed or content executed. Manifest includes source locations, byte counts
and SHA-256 values, not blob contents. Private directory/files use 0700/0600.

Scanner input modes are separate: Git patch history from immutable commit IDs
with `--full-history --no-ext-diff --no-textconv -m --root`, and directory scanning
of the additional raw blobs. The default Gitleaks 8.30.1 rule set is loaded from
an explicit minimal configuration; its built-in allowlists still apply. Inline
allow comments and ignore files are bypassed. Reports use `--redact=100`, default
decode depth 5, archive depth 0, and an explicit timeout. The manifest records the
scanner executable hash and configuration hash. No fetch or remote command runs.

This is **not** coverage of remote-only refs, reflog-only/dangling/unreachable
objects, pruned/deleted objects unavailable locally, non-Git dirty/untracked or
ignored files, resolved LFS payloads, nested archives, semantic binary content,
Docker images/layers, runtime logs or deployed configuration. The commit-object
inventory is not a claim that Git renders every reachable binary blob into a
text patch. Rule-based scanning is not universal proof of absence of secrets.

## Preparation evidence and review

- Initial preparation was deliberately terminated after review identified that
  `git hash-object` should not be allowed to apply configured filters. Capture
  `git-all-refs-inventory-20260921.json` records exit -15 in 98,253.167 ms, not a
  timeout or success. No scanner had run. Its private files remain preserved;
  effects of any potentially applicable prior filters were not retroactively
  disproved. No application/DB/provider command was intentionally invoked.
- The revised script explicitly disables replacement objects, global/system Git
  config and prompts. It removes `hash-object` entirely and uses raw in-process
  object hashing. A fresh private directory separates the verified attempt.
- Verified inventory capture exits 0 in 56,325.694 ms with no timeout, truncation
  or stderr. Reviewer accepts the raw-object safeguard. Two initial review
  concerns were withdrawn: the intentionally tracked manifest is metadata-only
  and exclusive-created; nonrecursive `mkdirSync` already rejects an existing
  directory/symlink before writes. No unsupported suppression was added.

## Result and remaining authority

Both scanners completed without timeout/truncation. History reports 3,095
scanned commits / 368,025,749 bytes / 711 matches in 399,800.426 ms; tree blobs
report 110,918,318 scanned bytes / 42 matches in 15,844.436 ms. Both exit **1**,
retained as findings, not clean scans. Scanner byte counts are not equated with
raw-object sizes. Metadata projection verifies every Secret field is REDACTED,
every history match belongs to the frozen graph and every tree match maps to a
copied blob. Input validation rechecks all 938 blobs, scanner/config hashes and
permissions; it passes in 3,858.994 ms.

Priority inspection covers 20 history locations: two contain the same service-role
JWT material, one stores opaque Wordstat access-token material, and 17 contain
the same anon-role JWT material. Decoded claims/storage context are **not**
signature verification, validity/revocation evidence or proof of safe historical
RLS. The sidecar's PUBLIC_ANON label distinguishes the declared role, not a
blanket false-positive clearance. No values, claim payloads or token hashes are
emitted. The other **733 matches remain UNREVIEWED** (691 history + 42 tree).
The immutable metadata projection retains its initial UNREVIEWED fields; the
priority-triage sidecar adds these 20 bounded classifications separately.

**Coverage reconciliation remains incomplete:** 3,117 graph commits versus
3,095 reported by Gitleaks. Raw-diff metadata finds 3,112 nonempty commits;
numstat variants find 3,085/3,087 with additions. Neither explains the exact gap.
A known-empty-commit diagnostic confirms zero can be reported and notes omitted
no-addition commits, but does not reconcile all 22. Its retained ERR-level log
comes from a Darwin temp-directory stderr warning; it is not a clean log.
Do not claim complete all-object/all-ref security coverage from these counts.

SEC-HISTORY-01 is corroborated offline; revocation stays unknown. Next: classify
remaining exact metadata rows, prioritizing tree finding14 (temporary integration
script) and historical debug captures, then resolve scanner count semantics.
Reuse existing evidence; do not repeat full scans just to recreate it. No key
testing, rotation, publication, deletion, suppression or history rewrite occurred.

Independent evidence review accepts this partial package with all limits intact.
Precommit capture passes in 5,010.376 ms: 26 owned staged paths, 1,874,762-byte
staged diff scan clean, 10 captures reconciled, current manifest/script hashes
equal recorded digests, unchanged statuses/historical verdict and nine foreign
paths excluded. This scans only the newly prepared evidence package. Final
27-file package adds that capture and its observed result notes, then receives
another exact-index/diff/secret check before local commit.

Original acceptance statuses and historical verdict remain unchanged. Native
aggregate/restore preparation still needs renewed permission; available Mac
space remains below the 10 GiB image floor. No DB, Docker, production, provider,
cleanup, push, deployment or history rewrite is authorized by this evidence.
