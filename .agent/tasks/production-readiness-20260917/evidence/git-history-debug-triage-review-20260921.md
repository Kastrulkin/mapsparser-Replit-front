# Frozen history debug-data triage — independent bounded review (2026-09-21)

## Result

**Evidence-method issue found — guarded recapture required before treating this capture as immutable-source proof.** The field binding and redaction design are otherwise suitable for a value-free triage ledger. This review does not classify any item as non-secret, active, usable, privileged, or revoked.

## Accepted bounded mechanics

- `git-history-debug-proof-20260921.json` completed (exit 0, no timeout or output truncation) and reports 572 selected `debug_data/` findings across 542 `commit:path` source specifications and 4,254,907 in-memory source bytes.
- The script compares the private redacted history-report SHA-256 with the metadata-held report digest; checks the report's 711-row count; binds each selected metadata row to the redacted scanner row (file, commit, lines, and rule); and verifies each returned blob's Git object SHA-1 before parsing it.
- It emits no candidate value or candidate/value hash. Its equality-group number only denotes equality among classified values, while its source SHA-256 denotes the full historical artifact. That is an appropriate metadata-only distinction.
- The classifier is deliberately conservative: it assigns a provider-field-material label only when one field/value candidate is found and, for JSON `hittoken`, the parsed `settings.hittoken` exactly equals that candidate. Other parsing/binding shapes remain `UNKNOWN`. The resulting counts are 510 `settings.hittoken` field-material rows, 26 HTML `aesKey` field-material rows, and 36 UNKNOWN rows, with 234 equality groups.

## Finding: frozen-object resolution is not hardened

**Priority: P2 — evidence-integrity / scope defect.** `support/git_history_debug_triage_20260921.cjs` calls `/usr/bin/git cat-file --batch` for `commit:path` specifications without the frozen-read environment already used by the inventory tooling (`GIT_NO_REPLACE_OBJECTS=1`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and `GIT_TERMINAL_PROMPT=0`). A replacement ref or relevant Git configuration can alter revision/path resolution before object retrieval, so the current capture cannot independently guarantee that its bytes are from the intended frozen commit:path view.

**Isolated correction/check:** rerun the same metadata-only script with those environment variables supplied to `execFileSync`, retain this initial capture, and require the guarded recapture to reproduce report digest, row classifications/counts, and source-artifact bindings before it is admitted as frozen-history evidence. This is not a product or provider-access finding.

## Binding and classification limits

The line matcher uses redacted scanner-match containment after replacing candidate occurrences. The one-candidate condition makes it adequate to establish field material for this narrow ledger, but it is not a proof of a unique lexical occurrence where an identical literal repeats on the same line. Labels must consequently remain **historical provider field material**, not a determination of credential type, validity, privilege, purpose, ownership, current presence, or exposure impact. The 36 UNKNOWN rows remain unresolved pending their own exact-context review.

This review made no provider request, application/runtime import, test, database, Docker, deletion, history rewrite, staging, or commit. It does not change the prior history/tree unresolved inventory, AC6, or overall FAIL.

## Addendum — guarded verified capture accepted

`git-history-debug-proof-verified-20260921.json` resolves the evidence-integrity defect above for the admitted capture. It completed in 6,029.264 ms (exit 0; no stdout/stderr truncation), records a non-inherited Git child environment with `GIT_NO_REPLACE_OBJECTS=1`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, and `GIT_TERMINAL_PROMPT=0`, and records support-script SHA-256 `9b67a225b040c3edec658a4efa32fecc31d2d378fcbf88a1c248663a727527f3`; the current support file independently has that digest.

The verified capture preserves all 536 original material rows exactly (ID, blob, complete-artifact source SHA-256, classification, field/path, and binding flag) and adds bindings only for the former 36 UNKNOWN rows. Its complete 572-row ledger is: 510 `settings.hittoken`, 26 HTML `aesKey`, 8 HTML `clientKey`, and 28 JSON `ordToken` field-material rows, with 249 equality groups. There are no remaining UNKNOWN rows **within this selected 572-row debug-data subset**.

**Bounded acceptance:** use the guarded verified capture, not the initial capture, as frozen-history field-binding evidence. The initial capture remains retained contextual evidence of the missing explicit child guard. All four labels remain historical provider-field material only: they do not establish non-secret status, current activity, validity, expiry, privilege, provider purpose, ownership, revocation, or remediation outcome. This addendum does not reduce any broader scanner backlog or change AC6/overall FAIL.
