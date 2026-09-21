# SEC-WORKER-ARTIFACT-02 — diagnostics versus functional IPC

Parent `5ef5ba7e811d31d8599857929f2b79219c5954d4`. P1 before production,
high confidence in the selected reachable persistence/console boundaries.
Raw provider data, URLs, warnings and exception text previously entered five
diagnostic files and normalization/error logs. Truncation or secret-name regexes
cannot protect arbitrary private values carried by these inputs.

## Local correction

`src/worker.py` reuses the existing bounded, nonmutating shape/URL helpers for
`timeout.json`, `subprocess_no_result.json`, `apify_debug.json`, and
`validation.json`. `exception.txt` retains the fixed crash category but omits
exception text/traceback. Writer-failure/status-failure messages become fixed
events; normalization emits a key count/title presence instead of raw values.
JSON diagnostic format changes are marked `diagnostics_version: 2`.

`apify_result.json` is **not** a diagnostic-only file: the subprocess writes its
full result there, passes its path through the queue, and the parent reads it
back as the actual card result. That protocol and its raw data remain unchanged.
The in-memory `apify_debug_payload` is preserved for cost settlement; validation
data and title fallback are preserved. No repository readers were found for the
five changed diagnostic files. Reduced forensic detail is intentional.

## Causal evidence and harness corrections

All evidence uses synthetic markers, in-memory files and extracted AST branches;
worker top-level imports, real processes, browser, DB and provider never run.
An audit hook rejects sockets/process spawning/SQLite. This is not integration
proof of the entire worker.

- `worker-artifacts-red-20260921.json`: first 10-test attempt had two ambiguous
  AST-selector assertion failures alongside privacy failures; not authoritative.
- `worker-artifacts-baseline-20260921.json`: selector corrected and IPC positive
  added; 11 tests, 9 failure entries plus 2 harness local-variable errors.
- `worker-artifacts-causal-baseline-20260921.json`: corrected final harness,
  **11 methods: 9 fail / 2 pass, 11 failure entries including subtests, 0 errors**.
  Source is exact parent worker; no source reversal was performed.
- `worker-artifacts-green-20260921.json`: same final test bytes, **11 pass**.
  Marker-free diagnostic writes and writer-error paths, original returned error
  URL, title/key values, in-memory provider/cost data and real extracted
  file-to-queue-to-parent JSON round-trip are asserted.
- `worker-artifacts-quality-20260921.json`: binds baseline source hash to the
  immutable parent Git blob, reconciles final test/helper/current source hashes,
  checks Ruff/diff, and proves unchanged AST for `_parse_card_via_apify`,
  subprocess entry, cost extraction and settlement functions. Git's harmless
  temp-directory warning is retained in stderr, not suppressed or a test failure.

Final test SHA256 `73f6665495ddc75a26538dd8d3a1f0e1ff1893ac1ac022b3053bbc2b51620cf0`.
Parent worker SHA256 `21e02cc78241de155460f6a53279e569cf02dffc4e63439d5b17ced9f096f910`.
Fixed worker SHA256 `4e1a5483e48b475e5e734f84be0782628d3bfb0ca84213fab9097a5dc61041c1`.
No capture was overwritten. Exact commands/timings/output remain in the JSONs.

The later docs/checkpoint reconciliation was independently approved without
promoting readiness. Precommit capture1806.878ms verifies23owned files and
133666staged diff bytes,8captures/13hashes, strict secret scan, nine foreign
hashes and original acceptance/historical-verdict equality. Final packaging
adds that capture (24files) and repeats verification.

## Independent review and limits

The read-only reviewer traced IPC consumers, billing and validation contracts,
then approved all five artifact changes and their tests with no actionable
blocker. The reviewer did not run integration tests. A review message called
the baseline a working-tree reversal; root corrected that unsupported wording:
the baseline was recorded before the patch and its bytes match the Git parent.
After checking the quality capture the reviewer explicitly withdrew that wording
and confirmed the corrected provenance and bounded approval.

Final adjacent-suite capture `diagnostic-artifacts-final-20260921.json` reports
49 passed and 4 subtests passed in1.51s (1806.857ms wall). This includes the
11worker artifact methods,4legacy orchestration methods and34previous pure
parser/worker checks, not a full backend aggregate. Thirteen source hashes are
reconciled by `diagnostic-artifacts-quality-20260921.json` (266.784ms).

Raw IPC storage/access/retention, service-level Apify debug writers, other worker
coverage/error logs, persisted proxy/queue reasons, leaf legacy parser logs,
historical artifacts and deployed code remain separate open boundaries. Do not
claim all debug directories or all worker output are sanitized. Whole readiness,
original AC statuses and historical verdict remain unchanged. No production,
native DB/restore, Docker, provider, cleanup, push or deployment action occurred.
