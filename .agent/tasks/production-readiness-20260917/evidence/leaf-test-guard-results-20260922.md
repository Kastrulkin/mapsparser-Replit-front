# TEST-LEAF-GUARD-01 — scoped test guard, causal fix

## Finding and correction

The current full offline run found33 later tests raising AssertionError from
`LegacyParserLeafDiagnosticLogsTests.setUpClass`. Its `sys.addaudithook` cannot
be removed and continued blocking process/socket/database API use after the class.
This made unrelated tests fail and obscured their actual behavior. PriorityP2,
high confidence, test-suite-only scope; no runtime application defect claimed.

Only `tests/test_legacy_parser_leaf_diagnostics.py` changes: each test now creates
an ExitStack, registers its close with unittest cleanup before patching, and denies
the exercised network/process/SQLite entry points until cleanup. Both connect and
connect_ex are covered. Three new tests exercise active denials, restoration and
exception-path cleanup; sockets close explicitly. Original three diagnostic tests
and their parser assertions remain unchanged. This is not a general sandbox for
arbitrary aliases/native code; the outer OS sandbox remains the safety boundary.

Baseline test SHA-256 `86d6651a6e9c4deeeb38a3307fb63a0f40a8c46194a6aba5a422ad88e1dd5a70`;
patched `152c0163f04a4072b469c7a36883a947a3ea49cca7785459e6abbc5b6c32b422`.
Runtime parser source stays unchanged at
`3a069c6724f31990792d74ff217e19ded6a39e24a0512139e4ea21fe9ef423c5`.

## Exact causal verification

Same harness SHA334d7d6e635cf91f253e6843965055a7b8d75e498d8b9ea19c2982d332cf813a
runs the same original3-test class followed by a socket probe. Both runs have
network/unowned-write denial and clean environment; only source read root changes.

- RED: original3pass, then leaked hook AssertionError; semantic exit1,534.811ms.
- GREEN: same3pass, then expected OS denial without leaked AssertionError;
  exit0,544.823ms.
- Expanded target file:6pass, no leaked hook, exit0,537.312ms.
- Ruff, compilation and diff-check pass. Independent code/causal review PASS.

Root additionally selects the exact33 previously hook-blocked nodes after the
six leaf tests. Adjacent v2:38pass/1fail,33.61s pytest/34.299s captured, no skip or
truncation and no leaked hook. It is deliberately NONPASS. The remaining failure
is the fake restore-helper mixed loopback/non-loopback binding test. Separate
diagnosis confirms a previously hidden fail-open here-string admission bug when
shell temporary-file creation fails; that correction is a distinct pending patch.
No real Docker/DB call occurred: the fixture supplies a fake Docker executable.

Adjacent v1 is preserved: collection failed before tests because the harness
omitted import-only DSN and Path normalization changed a URI parameter ID. V2
uses string concatenation for node IDs and the same unreachable localhost:1
metadata DSN as the full offline run. It does not change product contracts.

Artifacts: `leaf-test-guard-20260922/`, exact raw captures, harnesses, policies,
and manifest. No whole-suite green/production-ready claim, existing DB/provider
mutation, push/deploy or repeated cleanup. All13foreign paths remain separate.
