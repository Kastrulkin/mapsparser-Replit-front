# Full current-source offline diagnostic — 22 September

## Result: NONPASS

One complete collection of5,487 unique scenarios ran against base
`e44bd538ecf6ce19012df310a36f818915205077` plus exactly the two previously verified
parser/author test overlays. It is not the whole dirty tree or current production.
Independent comparison of all6,164 tracked files found only those two differences,
no missing/extra files or symlinks. The source manifest remained unchanged.

| Outcome | Count |
| --- | ---: |
| Call passed |4347|
| Call failed |44|
| Setup failed |4|
| Skipped during call |29|
| Skipped during setup |1063|
| Collection errors |0|
| Passing subtests, additional to scenario count |14|

Child exit1,67.139 seconds; wrapper70.154 seconds. No timeout, disk-floor abort,
or output truncation. The sum4347+44+4+29+1063 is5487; passing subtests are not
added to that total. There are5487 setup/teardown records and4420 call records;
1067 missing calls are explained by setup skips/failures. This is not a green
whole-suite, integration or production-readiness result.

## Failure families

-33 later failures originate at `tests/test_legacy_parser_leaf_diagnostics.py:185`:
  a permanent `sys.addaudithook` continues rejecting subprocess operations after
  that test class. This is a different file from the already corrected foreign
  `test_legacy_parser_diagnostic_logs.py`. A new scoped fix is being prepared;
  this evidence does not claim it fixed.
-11 `PermissionError`, errno1: ingress proxy5, compiled runner5, Telegram polling1.
  The offline sandbox intentionally denies their required capability. Three runner
  bind cases now retain original PermissionError instead of masking it with
  AttributeError, corroborating the earlier initialization fix without certifying
  real listener behavior.
-2 Vite harness RuntimeError cases; frontend-dist integrity1; module-size ratchet1.
  These require their appropriate built/frontend/integration prerequisites or
  separate focused diagnosis. They are not silently skipped or counted green.

The six earlier explicitly scoped parser4/child-guard1/author1 cases each have
passing setup/call/teardown in this full run. No arithmetic is added to earlier
frozen-baseline coverage.

## Strict node accounting qualification

V9 reports `node_drift` because two collected parameter IDs (indices2576/2577,
DOCX/XLSX fixtures) embed generated ZIP timestamps. Independent review applied
the existing timestamp-only equivalence checker and confirmed equal payloads
apart from that metadata and no other node/order drift. The original raw
callback and node list remain intact; v9 is not retroactively labelled PASS.
Its additional missing/unknown-stage reason comprises1067 expected absent calls
plus the six stage identities for those two raw timestamp variants. After that
verified mapping there are no missing/extra setup or teardown records.

The equivalence checker is the pre-existing
`support/native_fixture_inventory_hflypi.py:timestamp_normalizations`, SHA-256
`57492061f6d403787c15fc0bfb1c6b84e55dbf0dd9579781a75b829b95582c4e`.
It returned exactly `docx`, `xlsx`, validating unchanged non-time ZIP fields and
payloads. Its pinned `tests/test_media_upload_signature_security.py` hash
`8db6d00ff4846327b2501b807fbcdc2727d652afb5b2adbc558a4fe6e06ea4cb` matches
this snapshot. This does not relax v9 or certify skipped scenarios.

## Isolation and provenance

Exact executed runner is `runner_executed.py.txt`, SHA-256
`c6d2091d8081378bdcd781acd875be28efe35f5b146f8a0e2ee23425b628fbde`.
Pinned policy/nodes/source manifest are in the same artifact directory. V9 imports
none of the worker's earlier subsequently edited preflight helper. Those v6
outputs are input data only, independently checked again before/after execution.

Nine pure accounting controls and eight OS probes pass: owned-write positive;
source, user-read, TCP, Docker socket and symlink-escape denial; native nc denial;
exact symlink target. Named tmux `audit-current-full-v9` runs with clean environment,
no dotenv/user site/cache plugin, inherited network/user-read/unowned-write denial,
5GiB start/2GiB live floor,900-second deadline and process-group cleanup. Output
is concurrently drained with16MiB caps; only digests/counts and safe callback
coordinates are retained, never raw test stdout/stderr or exception messages.

Independent pre-execution and post-execution reviews PASS for diagnostic safety,
provenance and truthful accounting, not for the failing suite. Earlier preflight
failures (terminal reporter disabled, callback capacity, incomplete full-mode
implementation) remain privately retained; none is a product failure or full run.

Next: causal minimal fix for the leaf-test permanent hook, then exercise unresolved
capability-dependent families on an appropriately isolated integration profile.
No production, existing DB, provider effects, push/deploy or repeated cleanup.
