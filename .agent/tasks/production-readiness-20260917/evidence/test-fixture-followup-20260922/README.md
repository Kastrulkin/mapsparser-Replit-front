# Backend fixture follow-up — 22 September

These are bounded diagnostics following the preserved **NONPASS** full run at
`d0ef4ce8`. The media-ID fix and that full evidence were committed separately as
`45393b30`; its exact staged scan returned0/0findings in20.234s, local commit
exit0/0.208s. No push/deploy or production/provider action.

## Existing dirty candidates: independently accepted causal diagnosis

`verify_fixture_candidates.py` uses exact clean/archive and existing dirty-file
copies only, with unchanged reviewed v10 OS policy and process ownership.
Outer3.951334s/exit0; inner3.898s. No timeout or stream truncation.

- Author clean: the exact original call assertion at test line540 fails; setup
  and teardown pass. Existing dirty fixture:1test/3stages pass. It reaches the
  intended fingerprint/sender-account assertions with the added mock fields.
- Diagnostic logs: both copies pass4tests/12stages. The clean class leaves a
  permanent audit hook, so a following harmless subprocess is denied with
  AssertionError. Existing dirty per-test patches restore subprocess completion.
- Eight OS probes pass; child cleanup empty/clean, frozen6340-file source
  manifest and six copied input hashes unchanged. Independent runtime review PASS.

This does **not** adopt the two dirty files into the audit package. User choice
on adoption remains pending; originals were not modified or staged. The dirty
diagnostic patch lacks equivalent `socket.connect_ex` and available `os.spawn*`
denials and needs focused guard/teardown coverage before acceptance. Neither
this narrow proof nor previous scoped successes makes the full suite pass.

## Frontend integrity diagnostic

`diagnose_dist_fixture.py` calls existing test helpers on two synthetic dist
directories. Both missing and complete variants return1 because Bash cannot
create a temporary file for its inline-Python here document at shell line75.
Outer2.034107s/exit0 only means the diagnostic was captured; it is **not** a
successful integrity test. Raw stderr and exit codes are retained.

The missing-assets test originally accepts any nonzero exit, allowing this
unrelated prerequisite error to look like an expected rejection. Any fix must
preserve standalone script deployment (the deploy helper uploads only the
single shell file), retain asset traversal behavior, and require the expected
missing-asset reason in the negative regression test.

The first attempted comparison (`dist-fix-v1.json`, outer2.640451s/exit1)
did not reproduce the expected red failure: both old tests pass from a writable
copied tree. This is an **invalid red/green setup**, not a product pass or fix.
A separate2×2 matrix then compares identical script bytes at the original and
copied paths, each from the original read-only and copied writable working
directories. Both script locations fail only with the original read-only cwd;
both pass with the writable cwd. `dist-fixture-matrix-v1.json` retains all four
outputs. The next comparison must use the same original cwd on both sides.

**BUILD-DIST-TEMP-01 — locally FIX_PROVEN.** Same-cwd v2 completes3.919071s,
outerexit0. A collection hook sets the copied test module's `REPO_ROOT` to the
original read-only source on both sides; import-time `VERIFY_SCRIPT` still points
to each exact copied shell file. Old complete fixture fails with the original
heredoc EPERM, patched2tests/6stages pass, including the stronger missing-asset
reason. Python code after shell-unquoting is byte-identical to the old body;
only invocation changes to a shell string plus `python3 -c`. OS controls/source
and fixture hashes/cleanup pass. Runtime/deployment against production is not
claimed; script remains independently uploadable as required by its real caller.

## TEST-POLLING-HEARTBEAT-01 — FIX_PROVEN locally

Four polling tests instantiate the transport before replacing the global
heartbeat path. Constructor cleanup attempts to unlink the real fixed
`/tmp/localos-telegram-poll.heartbeat`; the offline policy correctly denies it.
The fixture change assigns a unique pytest temporary path for every test.
Product code, network mocks and all assertions remain unchanged.

V2 actual outer3.117515s/exit0: exactly4 original call failures, each
PermissionError/errno1 at `src/core/telegram_polling.py:27` on that global path;
all9 patched tests/27stages pass. After this, Ruff found15 pre-existing issues
(E701×5,E702×9,F401×1), identical before/after the functional patch. Mechanical
statement splitting plus unused-json-import removal clears all15; normalized
AST excluding that unused import matches the already-tested version.

Final V3 actual outer3.008599s/exit0 repeats the same four red failures and all9
green tests/27stages against final module SHA
`5d11ef067ed35c45d656385d645feee8406dc1fb6d568ecbf4fd7bb33ddfa86a`.
OS8controls, source manifest/fixture hashes and process cleanup pass. No real
heartbeat is read/written/deleted, and no real Telegram request occurs. V1
preparation was rejected before execution; its runtime is not claimed.

## Combined adjacent regression

`verify_fixture_combined.py` runs the three exact changed modules in one Python
process under the same policy: dist2,polling9,media13. Actual outer3.417772s/exit0,
24unique nodes/72setup-call-teardown reports pass; no skip,xfail or collection
errors. Source/input hashes unchanged, OS8probes and process cleanup pass.
Dist retains the same read-only cwd adjustment proven above. This checks adjacent
ordering of these fixes, not the full5516-node backend or live-provider behavior.

Restricted Google related-refresh and native finance-picker tests were not
run or altered. Existing foreign files remain outside owned changes.
