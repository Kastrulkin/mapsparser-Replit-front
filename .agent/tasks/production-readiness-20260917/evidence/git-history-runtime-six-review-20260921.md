# Frozen runtime-history rows 92–95, 684, 686 — 2026-09-21

Authoritative corrected capture: `git-history-runtime-six-proof-verified-20260921.json`,
exit0/462.090ms, no timeout/truncation/stderr. Initial proof exit1/370.538ms
rejects the original row684 interpretation and remains retained. Remaining
unclassified/UNKNOWN queue:115history plus tree11 =116.

## Method and report-index binding

This is a read-only, value-free review of the immutable
`history-redacted.json` report and exact Git blobs. Report row IDs are
one-based (report-array index + 1). For each row, the review:

1. verified the report commit/path/line tuple;
2. resolved `git rev-parse <commit>:<path>` to the blob listed below;
3. read only that frozen source line in memory;
4. reapplied the inherited Gitleaks v8.30.1 `generic-api-key` rule in memory;
5. checked AST binding of its captured value group without emitting a value;
6. compared the historical blob to the path at `074ee5a0`.

The exact assertions and metadata-only output are implemented in
`support/git_history_runtime_six_20260921.py`; it pins the frozen report SHA,
uses isolated no-replace Git `cat-file` reads, and emits blob hashes and
classifications only.

The retained report masks the scalar but retains surrounding Match text.
Root's follow-up reconstructs the whole Match by replacing the single captured
scalar with REDACTED: all six are byte-equal to the frozen report Match. Thus
binding does not rely solely on a singleton regex candidate. The discovery
regex is a Python transcription, not a general cross-engine equivalence claim.
No value or value hash is emitted. Git children use an explicit isolated
environment and raw blob-header SHA1 is checked against the object identity.

The content predicates additionally bind the exact-line constant to field
`key` inside the named static approved-content collection, with identifier
grammar and no call expression. The hardened argument check exposed an error
in the initial review: row684 is the second positional argument (a default
value), not the first argument naming the environment variable. The original
five-nonsecret claim is withdrawn. The failed proof capture370.538ms is retained;
the corrected method classifies four nonsecret rows and two UNKNOWN rows.

## Results

| Frozen row ID | Frozen blob | In-memory semantic binding | Classification | Current `074ee5a0` blob relation |
| --- | --- | --- | --- | --- |
| 92 | `ffdbb90ac1f603d7a9ac6968c20978614236913d` | Exactly one candidate; exact static string constant in a static approved-content collection, dictionary field identifier `key`; no environment or network expression. | `HISTORICAL_STATIC_CONTENT_KEY_LITERAL_NONSECRET` | different |
| 93 | `ffdbb90ac1f603d7a9ac6968c20978614236913d` | Exactly one candidate; exact static string constant in a static approved-content collection, dictionary field identifier `key`; no environment or network expression. | `HISTORICAL_STATIC_CONTENT_KEY_LITERAL_NONSECRET` | different |
| 94 | `ffdbb90ac1f603d7a9ac6968c20978614236913d` | Exactly one candidate; exact static string constant in a static approved-content collection, dictionary field identifier `key`; no environment or network expression. | `HISTORICAL_STATIC_CONTENT_KEY_LITERAL_NONSECRET` | different |
| 95 | `969041f311e37d40f9faad703b530a9eee9af2a1` | Exactly one candidate; exact static string constant in a static approved-content collection, dictionary field identifier `key`; no environment or network expression. | `HISTORICAL_STATIC_CONTENT_KEY_LITERAL_NONSECRET` | different |
| 684 | `45df763c0508861fc7dfa868812be5e38d5f8fdd` | Exact static string constant is the second `os.getenv` positional argument: fallback value, not variable name. No exact placeholder/nonsecret proof. | `HISTORICAL_ENVIRONMENT_DEFAULT_LITERAL_UNKNOWN` | different |
| 686 | `1210ba4092a367897460e25a2c7f1bad565c891c` | Exactly one candidate; exact static string constant is passed as constructor keyword identifier `client_secret`. It is not an environment-variable-name binding and no placeholder/nonsecret semantic proof was established. | `HISTORICAL_HARDCODED_CLIENT_SECRET_LITERAL_UNKNOWN` | different |

Only rows92–95 meet the nonsecret standard through exact source-value semantics,
rather than filename or test provenance. Rows684 and686 remain UNKNOWN: default
and credential argument positions do not prove placeholder or nonsecret values.
Independent source review accepts the four bounded content-key classifications;
root and the original reviewer both reject the earlier argument-position error.

## Limits

All six current paths resolve to different blobs at `074ee5a0`; this frozen
history classification is not a current-source finding or a current-source
clean bill. No app/provider/DB import, network call, scanner rerun, deletion,
or credential validation occurred. The unknown rows684 and686 remain in the
canonical security count pending independent value-safe proof or credential
rotation/revocation evidence.

## Independent final-method acceptance

**BOUNDED ACCEPTED.** `git-history-runtime-six-proof-verified-20260921.json` completes successfully (exit 0, 462.090 ms, no timeout/truncation/stderr) with the frozen report digest, exact commit/path/line binding, isolated no-replace Git reads, raw Git-object verification, one candidate on each exact line, and equality of the complete redacted scanner Match after replacement. It emits neither a candidate value nor a candidate-value hash; recorded hashes identify complete source blobs only.

The hardened argument-position check correctly withdraws the prior row 684 non-secret conclusion: it binds the candidate as the second `os.getenv` argument (a default), not its environment-variable name. The four rows 92–95 remain sufficiently classified as non-secret **only in their exact frozen static approved-content collection context**. Rows 684 and 686 remain UNKNOWN; default-value and `client_secret` argument positions cannot establish a placeholder, non-secret semantics, validity, privilege, expiry, or revocation.

The corrected arithmetic is accepted: 115 remaining history rows plus tree row 11 equals 116 unresolved rows. This addendum is not a current-source absence claim, an all-history clearance, a credential test, or an AC6/overall-PASS promotion. The initial failed proof remains important evidence of the corrected methodology rather than a successful result.
