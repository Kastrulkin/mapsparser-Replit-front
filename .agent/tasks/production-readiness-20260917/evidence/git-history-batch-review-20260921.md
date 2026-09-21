# Frozen history batch review — 2026-09-21

Parent: `fdbabac4d830cb82d3ec2ffcb0f884b6250c141a`.
This is additive evidence for the frozen `7cf0cd24` scan, not a new scan or
whole-project security verdict. The original scan reports and exit codes remain.

## Root execution and independent review

The root read both scripts before execution. The independent access reviewer
identified an unbounded output field in agent44: a historical JSON property was
printed as a reference path. Root removed it before the first execution. No
claim is made that the field actually contained confidential material.

The first output40 capture failed with a sanitized `CalledProcessError`
(91.36 ms). It is retained, not used as a pass. The repair distinguishes an
explicit successful empty `ls-tree` result from a failed Git command; only the
former proves a missing artifact. Both final scripts use literal pathspecs and
full-tree listings. Other source/object/Git failures remain fatal.

| Verified capture | Rows | Exact historical file digests, nonsecret | UNKNOWN | Duration ms |
| --- | ---: | ---: | ---: | ---: |
| git-history-agent44-proof-verified-20260921.json | 44 | 35 | 9 | 3280.118 |
| git-history-output40-proof-verified-20260921.json | 40 | 24 | 16 | 2563.530 |

Both verified commands exit 0 without timeout, output truncation or stderr.
Every positive classification requires raw Git object identity, the exact
frozen report/line/masked whole-match binding, parsed JSON association and
equality to the SHA-256 of the referenced file at the historical commit. A
digest-looking value, output directory or field name is insufficient.

The independent frontend reviewer read the final scripts and all four captures,
confirmed all 59 positive predicates and preserved 25 UNKNOWN results, and
returned bounded `NO_BUG_PROVEN`. Eight agent44 and six output40 unknown rows
have explicitly missing referenced artifacts; other unknown rows lack the
required semantic/equality proof. No candidate values, candidate hashes, raw
Match/Secret text or access URIs are emitted by these verifiers.

## Reconciliation and limits

Later in the same package, the verified misc26 proof adds11nonsecret
classifications (8explicit placeholders and3same-scope record UUIDs), retaining
15UNKNOWN. Quality replay reconciles all110 new rows:70clear/40UNKNOWN. Current
queue becomes46 (45history plus tree11). See the misc26 review and quality capture;
the preceding84-row reviewer arithmetic below retains its checkpoint scope.

These 59 new nonsecret proofs reduce the prior 116-row unclassified/UNKNOWN
queue to 57 (56 history findings and tree row 11), before any later misc-row
proof. This is not the remaining security-risk count. Previously classified
privileged/provider material and credential lifecycle risks remain open.

No historical source was executed, no app/DB/provider was imported or called,
and no scanner rerun, history rewrite, deletion, Docker or production action
occurred. Original acceptance statuses and overall FAIL remain unchanged.

Exact commands are in the named captures; final source hashes are reconciled
by the package quality check. The regex is a candidate-discovery transcription,
not a claimed general cross-engine equivalence proof.
