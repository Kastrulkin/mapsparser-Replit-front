# Frozen provider-debug findings — 21 September 2026

Parent `bf277dbf8125c4b6ce37a2edb8dff64780926ab1`; original scan remains frozen
at `7cf0cd24`. This is additive classification, not a new scan or a clean-history
claim. The previous turn made progress through the Docker-context correction.

## Verified scope

`git-history-debug-proof-verified-20260921.json` records exit 0 in 6,029.264 ms,
without timeout, output truncation or stderr. The stdlib Node support script
reads 542 immutable commit/path specifications (4,254,907 bytes) for all 572
debug-directory rows in the original 711-row history report. It verifies the
report SHA-256, exact metadata alignment, raw Git blob-header SHA-1 and complete
source hashes. The Git child uses an explicit isolated environment, disabling
replacement objects and global/system configuration. No captured source is
executed and no URL is requested.

The complete scanner match binds after replacing the unique candidate scalar
value, not merely a guessed word or a column offset. JSON findings also bind
to parsed object fields. Repeated lexical occurrences on the same line are not
claimed to have distinct identities. Reported equality groups compare values
in memory only; neither values nor value hashes are emitted.

| Historical field | Rows | Classification scope |
| --- | ---: | --- |
| `settings.hittoken` | 510 | Provider JSON field material |
| `aesKey` | 26 | Provider HTML field material |
| `clientKey` | 8 | Provider HTML field material |
| `ordToken` | 28 | Parsed provider JSON field material |
| Total | 572 | 249 distinct values across these locations |

**None of these labels means non-secret, active credential, privileged access,
safe public identifier, expired or revoked.** Purpose and lifecycle need separate
evidence. The historical Git content remains retained; no deletion, rewrite,
rotation, publication, provider call or production operation occurred.

## Earlier observations and independent review

The initial capture `git-history-debug-proof-20260921.json` exits 0 in 4,303.990
ms with 510 + 26 field bindings and 36 UNKNOWN rows. Its launcher supplied the
Git guards, but they were not self-contained in the captured script command.
Independent review requested an explicit child environment. The verified
successor adds that boundary and names the other two fields. All 536 initial
material rows preserve their blobs, source hashes and prior classifications.
Both captures are retained; use the verified successor as authoritative proof.

The independent report is `git-history-debug-triage-review-20260921.md`.
The planning report is a pre-triage grouping, not a mutable security verdict.
Tree row 11 still has no defensible semantic disposition; the additional
value-free examination is recorded in `git-tree-unknown-followup-20260921.md`.

## Remaining work

Of 711 history rows, 20 had prior priority classification and 572 now have
provider-field classifications; **119 history rows remain unclassified**.
Together with tree row 11, there are **120 unclassified/UNKNOWN rows**. This
reduction from 692 is triage progress, not elimination of 572 security risks.
The ten tree image-access components, historical privileged-role/Wordstat
material and their unresolved owner/provider lifecycle gates remain open.

Current-source review also identifies the conditional raw debug-bundle producer
candidate `SEC-DEBUG-BUNDLE-01`. Its status and tests are tracked separately:
historical field matching alone does not prove a current runtime leak.

Original acceptance statuses, immutable historical verdict and whole-goal FAIL
remain unchanged. Native aggregate/restore permission and Docker disk gates are
not bypassed. Nine unrelated worktree paths remain untouched.
