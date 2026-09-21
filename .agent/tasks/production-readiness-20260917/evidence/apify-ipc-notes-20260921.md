# Apify IPC checkpoint notes — 21 September

Parent: `d8631fec6f054f3a25bc820ed456e71e608974f0`.

## Local result

- SEC-APIFY-IPC-01: named raw `apify_result.json` persisted the functional
  result in a debug directory. Current transport keeps that private result in
  an anonymous temporary file and signals readiness through a small Queue item.
- REL-APIFY-IPC-01: a real owned synthetic ~680KB result previously timed out
  through Queue/join when debug was disabled. Final immutable-parent proof is
  4 failures/0 errors; current final test is 11 passes.
- Final SHA-256: worker
  `08387e39b6d024e11f22de6715fc70121281c6efbb7f28ce801bdb713acb3241`; test
  `c490c7f3f982978d890b024d00bc2634fc4004140debaeefcc35783bced84be2`.

## Provenance and limits

`apify-ipc-verified-baseline-20260921.json` and
`apify-ipc-verified-green-20260921.json` compare the same four causal cases;
the latter also runs seven hardening cases, not all valid on the parent's old
three-argument internal API. The final tests are frozen across both captures.
`apify-ipc-broad-20260921.json` records93passes +4subtests in11.77s/captured
12633.373ms, with before/after source hashes equal. It forbids `.env`, network,
subprocess, DB and provider access and does not import full worker; one owned
synthetic fork is intentionally exercised. `apify-ipc-adjacent-final-20260921.json`
adds 11 artifact checks and one exact existing child test.

Quality capture411.773ms: all three changed test files pass full Ruff; worker
passes F821/F822/F823; diff passes and the complete worker AST outside the two
IPC functions and queue/tempfile imports equals the immutable parent. The
manifest binds21source/test hashes and10capture hashes. Independent bounded
runtime/test review and separate evidence reconciliation accepted final bytes.
The fake unkillable-process case prints a static warning; it is not an observed
real orphan. One synthetic real fork verifies ordinary large-result completion.

Both findings are P1/high-confidence at this reachable boundary: debug runs
retained unnecessary raw results; large no-debug responses could discard a
completed parse as timeout. Blast radius and effort are bounded to two internal
functions plus three tests; compatibility risk is controlled by full payload,
cost, error and cleanup assertions. No public HTTP/schema contract changes.

Keep all seven earlier IPC captures. Initial red is3fail/1pass. Two retained
final-baseline/final-green captures stopped before tests on harness hash drift;
they are provenance only, not product failures. No capture is overwritten.

Initial precommit strict scan reported one generic-key candidate: a heading
containing the provider name followed by the parent commit abbreviation. The
staged line and Git parent establish it is not a credential. The heading was
rephrased without suppressions or scanner allowlists; the failed capture is
retained separately from the final gate.

The patch does not change billing, retry, card or provider-cost data. It cannot
guarantee OS-level child termination, remote actor cancellation, secure erase or
historical artifact deletion. Parent owns FD0600 and bounded terminate/kill
cleanup. This is not a production, DB, provider, Docker, aggregate, restore or
release-gate result.

## Separate next candidate

`_validate_parsing_result` constructs a reason from untrusted error/message text;
normal terminal failure later persists that reason to `parsequeue.error_message`.
Scoped Operator and superadmin queue readers expose the column. This is source
review only, neither reproduced nor fixed in the IPC package.
