# Native sandbox aggregate baseline — 22 September 2026

This package preserves a whole frozen-collection sandbox attempt, not a
product-correctness, integration, coverage-union, current-source, or release
claim. The source tree was frozen at
`99849935de26e2932613f2a73cf515dff49104a1`; the canonical inventory is
`native-fixture-inventory-v4.json` (SHA-256
`e49b7a637b77af2c437d7fc2a7f9190c81f81c82da2d1a22fbcab13ed1dedb52`).

## Full v1 result

`native-sandbox-full-v1.json` records a 70.846-second attempt over all 5,481
collected frozen node IDs. It completed collection with zero collection
errors, but pytest exited 1: 4,338 call passes, 47 call failures, 4 setup
failures, 1,092 skips (29 call and 1,063 setup), and 14 recorded subtest call
passes. The suite therefore **failed**. This archive does not diagnose those
failures as product defects and does not promote any node set into an accepted
coverage union; reconciliation with previously accepted nodes remains pending.

## Full v2 confirmation

`native-sandbox-full-v2.json` repeats the whole 5,481-node frozen attempt with
the current diagnostic helper (SHA-256
`d262b9003fdf010a1933ae53336185d496a259695a7ddcd93a10f0ba4286ca76`). It
again completed collection with zero collection errors and the same result
counts—4,338 call passes, 47 call failures, 4 setup failures, and 1,092
skips—but exited 1 after 69.378 seconds. The 51 failing node identities are
the same as v1. It is a confirmation of this sandbox-run baseline, not an
aggregate pass or a fix claim.

The safe exception-frame diagnostic groups those 51 identities as follows:
33 end at the frozen global `sys.addaudithook` path in
`tests/test_legacy_parser_diagnostic_logs.py:111`; 10 are permission failures
(7 source-guard binding, 2 compiled/tmp, 1 Telegram heartbeat); 3 are runner
`AttributeError` cases involving `server_close` before pool initialization; and 5 are other
assertions (author 1, child guards 2, frontend dist 1, ratchet 1). This is a
source-bound classification of where each captured failure terminates, not a
demonstrated causal diagnosis. In particular, the existing foreign-worktree
scoped `ExitStack` patch is not changed or staged by this package.

The independent runtime-integrity review recorded 5,720 frozen blobs both
before and after, unchanged guard SHA-256
`07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150`, an
unchanged canary, and an absent forbidden source path. The sandbox probe in
the full capture records all ten isolation controls passing, including denied
network, Docker socket, unowned writes, symlink escape, and user-workspace
read. These are harness-isolation observations only; they do not establish a
passing application test run.

## Control chronology

The controls are preserved because the initial sandbox assumptions were
falsified before the later successful controls:

| Capture | Result recorded | Meaning retained |
| --- | --- | --- |
| `native-sandbox-controls-v1.json` | failed: child exited `-6` (SIGABRT) | first control design was not accepted |
| `native-sandbox-controls-v2.json` | failed: `native-child-network-denied=false` | native child stderr shape made the assertion false |
| `native-sandbox-controls-v3.json` | passed: 9 checks | added nc verbosity; same denial assertion now has stderr evidence |
| `native-sandbox-controls-v4.json` | passed: 10 checks | adds denied user-workspace read; same archived helper as full v1 |

The v1, v2, and v3 helper source bytes were not snapshot-archived. Their
raw captures record only these helper SHA-256 values, respectively:
`5cf529ec1d8568b2e025851da620ff11fd15e179759962df50be150378e43306`,
`abb35dc72da7b11a43d9d8c56651b8afd404c7dad6affea3b187d68d0abdd1f8`, and
`8995492b284f0fd2fc7039e7e284745ed7c65191099281b9fa6e0ffcbcf5945e`.
For v4 and full v1, the exact helper source is preserved as
`native_sandbox_aggregate_v1.py.txt` (SHA-256
`3dcf55cb85efb1df53a7be8182ed22d94538c67f1245c3f53c9746e4a16d125a`). The
current helper is not substituted for that snapshot. Its SHA
`d262b9003fdf010a1933ae53336185d496a259695a7ddcd93a10f0ba4286ca76`
matches the executed v2 diagnostic hook; both current helper and pure outcome
controls are bound by the manifest. Pre-execution and runtime-integrity reviews
passed independently. No source/type/message output is included in the new hook.

## Package boundaries

`native-sandbox-hflypi-20260922/` contains byte-preserved raw JSON captures
and the exact v1 helper snapshot. `SHA256SUMS` binds those seven files and two
current support files. The
full-run captures retain only stdout/stderr byte counts and SHA-256 values,
not their contents; this report likewise reproduces neither stream. Safe
control outcomes are summarized above. No production database, provider,
Docker image, or external write is claimed by this baseline package.
