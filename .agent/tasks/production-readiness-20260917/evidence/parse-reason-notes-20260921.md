# Parse-queue reason projection notes — 21 September 2026

## Scope

SEC-PARSEQUEUE-REASON-01 was bounded to `_validate_parsing_result` error
results and the normal terminal/retry diagnostic reason boundary. Before this
change, arbitrary parser `error`/`message` input became the reason later
persisted to `parsequeue.error_message`. The selected local correction projects
that reason through the finite parsing-failure taxonomy. Within this diagnostic
path, raw error/message remains available in memory for legacy retry
classification; the functional card payload is unchanged.

The correction leaves normal SQL control flow, non-error validator outcomes,
captcha/closed/quality paths, retry caps, billing and parser data unchanged.
It does not claim to sanitize proxy/direct-DLQ/CAPTCHA/handler/warning writers,
old queue rows, historical artifacts or deployed logs.

## Evidence boundary

Parent: `6ac6dc915969fdd96c183be26ba527561b2f7560`.

Final bytes:

- worker SHA-256: `c1830f976d8831912559e4ce9caa77cd34a35aa131ca00104de34d04380277d9`;
- taxonomy SHA-256: `30d07b3b3c2119fd6fc46c27b69b9be1a78c1c96e2262db4b547dff931e63dcc`;
- final test SHA-256: `2867396ee4055b29456a38930e7945d8ae0378a87061747e2b00a312e54befb6`.

`parse-reason-verified-baseline-20260921.json` runs the final thirteen tests
against immutable parent worker and taxonomy bytes: eight assertion failures,
five passes and zero errors (1.754 s; captured 2175.900 ms).
`parse-reason-verified-green-20260921.json` runs the same thirteen current
tests: thirteen passes (1.807 s; captured 1886.423 ms).

`parse-reason-adjacent-final-20260921.json` passes ten existing validator/retry
functions in 306.656 ms. `parse-reason-broad-20260921.json` records 128 passes and
four subtests in 13.86 s / captured 14304.852 ms across 16 test files, with 29 hashes
stable before/after and no full worker import, DB, env file, network or provider.
The existing IPC synthetic fork remains intentionally allowed.
`parse-reason-quality-20260921.json` passes in 728.036 ms: scoped Ruff, worker
F821/F822/F823 and diff checks; worker AST outside the two scoped functions plus
taxonomy import, non-error validator behavior and retry caps/decisions remain
unchanged except the in-memory raw-alias input.

Eight captures are retained. `initial-green` used early worker `eefab…0665` and
the first adjacent capture intermediate worker `52d0…ae67`; they are provenance,
not final-byte proof. There were no captured harness-test failures. The manifest
maintained by the parent binds 29 source hashes and eight captures.

## Design and limits

Regex redaction could miss arbitrary PII. Terminal-only projection would still
leave retry/native-fallback diagnostics with raw detail. Finite validator plus
retry projection was selected because it preserves controlled reason codes and
legacy retry compatibility while keeping the raw policy input internal.

No production, DB, provider, Docker, cleanup, push or deploy action occurred.
Native aggregate/restore preparation remains denied and disk 4114304 KiB (~3.92 GiB)
is below the 10 GiB image floor. The original acceptance status remains AC1–9/11
FAIL, AC10 PASS and whole-readiness FAIL.
