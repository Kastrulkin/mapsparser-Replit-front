# Frozen history output-manifest rows 21–43, 45–61 — 2026-09-21

Root follow-up: the pending plan below is now executed by
`git-history-output40-proof-verified-20260921.json` (exit 0, 2563.530 ms):
24 exact historical artifact digests nonsecret, 16 UNKNOWN. The initial failed
capture remains. See `git-history-batch-review-20260921.md` for final independent
review and the distinction between unknown values and confirmed missing artifacts.

## Pending root execution

This is a bounded, value-free proof plan for exactly 40 one-based rows in the
immutable 711-row redacted report. The frozen report digest and the immutable
row-scope tuple digest are pinned in
`support/git_history_output40_20260921.py`.

For every selected row, the support script will require all of the following
before any non-secret classification:

1. the frozen report tuple and masked whole-match reconstruction bind to one
   candidate on the declared historical source line;
2. the declared `commit:path` resolves under an isolated no-replace Git
   environment and its raw Git object identity is verified;
3. the exact candidate has exactly one scalar association in parsed JSON; and
4. that JSON field yields a safe relative artifact reference whose exact blob
   at the same declared historical revision has SHA-256 equal to the candidate.

Rows lacking any one of those conditions remain
`HISTORICAL_OUTPUT_VALUE_UNKNOWN`. Output-directory provenance, a hex-like
shape, or a field name alone is intentionally insufficient.

The script emits only row IDs, boolean proof predicates, classifications, and
the immutable scope digest. It emits no scanner value, value hash, raw source,
Match/Secret text, URI, or source artifact digest. It has not been executed by
this reviewer.

## Initial capture and hardened missing-artifact handling

Root retained the initial capture separately as
`git-history-output40-proof-20260921.json`: it exited nonzero with a sanitized
Git child-process error before completing the row set. That initial evidence is
not overwritten. The support script now uses an isolated `git ls-tree` check
before reading each referenced artifact. Only a successful Git invocation with
an empty exact-path result is treated as a confirmed missing artifact and
therefore remains `HISTORICAL_OUTPUT_VALUE_UNKNOWN`. Any source retrieval,
revision resolution, `ls-tree`, or post-existence blob-read error remains
fatal. The non-secret condition is unchanged: it still requires a unique JSON
association and exact SHA-256 equality against an artifact blob at the declared
historical revision.

## Limits

This pending proof does not establish whether any historical material is
active, usable, privileged, owned by a provider, expired, revoked, or absent
from other history/current sources. It does not run the scanner, an
application, a database, a provider request, or a deployment.
