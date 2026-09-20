# Independent bounded supply-chain review — 21 September 2026

**Verdict: bounded evidence PASS; AC6 and whole readiness remain FAIL.** This
independent review uses already-captured data only. It did not perform source,
dependency, application, network, Docker, database, or credential operations.
It covers the committed `334c9d4b` archive and current frontend lockfile
captures, not an image, OS, history, log, or deployed-runtime review.

## Frozen committed-source secret scan

[`current-source-snapshot-verification-20260921.json`](current-source-snapshot-verification-20260921.json)
verifies the scan snapshot against commit `334c9d4b`: 5,417 blobs and
86,228,059 bytes, with no missing blobs, mismatches, or extras. It also binds
the redacted report by SHA-256 and confirms all 101 reported secrets are
redacted.

[`current-source-secrets-20260921.json`](current-source-secrets-20260921.json)
records strict offline Gitleaks 8.30.1 over that archive: 67.25 MB in
17,037.047 ms, exit 1 because 101 rule matches were found, with no timeout or
truncation. Exit 1 is a finding status, not a credential conclusion.

[`current-source-finding-predicates-20260921.json`](current-source-finding-predicates-20260921.json)
provides value-free classification evidence; the exhaustive sanitized ledger is
[`current-source-secret-triage-20260921.json`](current-source-secret-triage-20260921.json).
The 101 findings reconcile as:

| Classification | Count | Basis |
| --- | ---: | --- |
| SHA-256 integrity-manifest values | 83 | Every mapped value satisfies the 64-hex SHA-256 predicate; every location is recorded in the predicate capture. |
| Synthetic OAuth regression-output repeats | 3 | One captured test-output location repeated by the scanner; not runtime configuration. |
| Contract idempotency examples | 2 | Documentation contract examples, not authentication material. |
| Narrative/evidence prose | 5 | Security, readiness, UX, and example-copy text rather than runtime configuration. |
| Deterministic source/test fixtures | 7 | Seed/copy-contract keys and test fixtures; no runtime secret-loading path in this bounded review. |
| Legacy Wordstat documentation placeholder | 1 | The exact literal-placeholder predicate is true. |

**Result:** all 101 findings are non-secret for this frozen committed-source
scan; confirmed credentials and unknown findings are both zero.

I initially inferred the legacy Wordstat Authorization-header finding might be
a credential from header form. That was unsupported by the redacted report and
is withdrawn. The later frozen-source, value-free predicate confirms a literal
documentation placeholder. No credential value was copied, tested, or emitted.

This correction makes no claim about Git history, uncommitted files, Docker
layers/images, logs, runtime configuration, provider validity, or historical
credential revocation.

### Current branch delta

[`current-branch-secret-delta-20260921.json`](current-branch-secret-delta-20260921.json)
records the strict 131-commit delta from `30262a5` through `334c9d4b`: 5.87 MB,
10,245.786 ms, exit 1 for seven redacted findings, with no timeout or
truncation. Its authoritative reconciliation is
[`current-branch-secret-delta-verification-20260921.json`](current-branch-secret-delta-verification-20260921.json):
2,673.807 ms, exit 0, seven findings, a bound redacted-report hash, and exact
frozen-source excerpt checks. Three are synthetic OAuth regression output and
four are prose/example identifiers. The delta therefore adds no unclassified
credential finding.

This is a current-branch delta only. It neither clears baseline history,
other refs, historical revocation, nor image/layer/log exposure.

## Frontend dependency and license metadata

[`current-frontend-lock-audit-verified-20260921.json`](current-frontend-lock-audit-verified-20260921.json)
is the usable frontend npm advisory result: exit 0 in 1,920.909 ms, no timeout
or truncation, 528 total dependencies, and zero reported advisories. The first
configuration attempt, [`current-frontend-lock-audit-20260921.json`](current-frontend-lock-audit-20260921.json),
exited 1 and is retained as a failed configuration attempt, not advisory
evidence.

The first license-metadata capture,
[`current-frontend-lock-metadata-20260921.json`](current-frontend-lock-metadata-20260921.json),
has truncated stdout and is not parseable evidence. Use only
[`current-frontend-license-metadata-verified-20260921.json`](current-frontend-license-metadata-verified-20260921.json):
it is complete (exit 0, 759.034 ms), covers 528 lock entries, and confirms the
package and lock source remained unchanged after the audit. It reports 305
license declarations enriched only from matching-version installed metadata,
eight then-unresolved optional SWC platform packages, and two MPL-2.0 developer
tools. The resolution is now captured in
[`current-frontend-license-registry-20260921.json`](current-frontend-license-registry-20260921.json):
all eight exact optional SWC versions and `dist.integrity` values match the
frozen lock, in 10,703.626 ms with exit 0 and no truncation; one declares
Apache-2.0 and seven declare Apache-2.0 AND MIT. Combined declaration coverage
is therefore 528 entries: 215 lock declarations, 305 matching-installed
metadata declarations, and eight registry-resolved optional packages.

[`current-frontend-license-inventory-20260921.json`](current-frontend-license-inventory-20260921.json)
is the complete per-package/provenance ledger for those same 528 entries:
exit 0 in 573.153 ms, no timeout or truncation, zero unresolved declarations,
and SHA-256 metadata records for the 305 matching installed package manifests.
Both MPL-2.0 entries are developer tools.

This is license *metadata* inventory, not legal compliance, entitlement, fresh
artifact integrity, or installed-tree integrity. The registry capture used
public metadata only: no package was downloaded, installed, or executed.
Legal policy approval remains outside this review.

## Remaining AC6/release boundary

The evidence improves current committed-source secret triage and current
frontend lock advisory/metadata coverage only. AC6 remains FAIL pending
release-artifact/image and Linux/OS/native dependency, license, layer/log
secret, target-platform, and owner/legal decisions. Current disk headroom is
below the documented Docker image floor; this review neither authorizes nor
bypasses denied aggregate/restore or image lanes.
