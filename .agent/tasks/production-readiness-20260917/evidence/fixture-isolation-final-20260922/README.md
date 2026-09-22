# Final author/diagnostic fixture acceptance — 22 September

Parent `954979662e95fc45d026c9a5e9aa1c0413577325` on the readiness branch.
This is a bounded local test-fixture fix, not a passing full-project audit.

## Cause, changes and authority

The earlier [causal comparison](../test-fixture-followup-20260922/README.md)
already proved two failures: the author mock omitted the approved queue/touch
fields required to reach its fingerprint assertion, and the diagnostic class's
permanent audit hook denied a harmless process after its tests ended.
That original red/green is preserved, not rerun or reinterpreted here.

D-126 resolves the assistant-imposed optional adoption wait under the user's
original explicit reversible-local-fix authority. It is not new user consent or
a platform restriction override. Only two pre-existing dirty tests are adopted:

- Author SHA `21a1a4c9c3337bb516a8c80a354b860d6ba380bf1c4ce0aed4ba0bc5196f782c`
  is unchanged. Existing assertions, including changed-facts denial, are intact.
- Diagnostic final SHA
  `b654f5c74ef9f52c1b7e2add05f3dd7d08723feb135ec6dca1ee3f20a9519b18` keeps
  all four original test bodies. Per-test ExitStack cleanup now covers both
  socket methods, process entry points, available spawn variants and SQLite.
  Two added tests verify active denials, exact restoration and cleanup after
  a deliberately raised setup error. Original dirty SHA6b368126 remains at
  `/private/tmp/localos-legacy-diagnostic-guard-AqES9r/test_legacy_parser_diagnostic_logs.before.py`.

## Actual verification

One execution in named tmux `audit-fixtures-final-v1`: outer **3,610.001 ms**, exit0,
no timeout/truncation; helper3.545s, pytest child1.246s. Exact pinned manifest:

| Suite, in execution order | Nodes | Passed lifecycle phases |
| --- | ---: | ---: |
| Final diagnostic | 6 | 18 |
| Author, non-integration only | 18 | 54 |
| Already-fixed adjacent leaf diagnostics | 6 | 18 |
| Total | 30 | 90 |

All three pytest runs share one child process. Exact node/stage accounting has
no skips, xfails, subtests or collection errors. A real harmless Python subprocess
completes after all suites; the original leaked hook would deny that sentinel.
Both author PostgreSQL selectors are excluded, not counted as passed.

Eight OS isolation probes pass. Policy denies network, Docker, user-file reads
and source writes; only the designated temporary write root is allowed. Start
floor5GiB and live floor2GiB remain. Both owned process registries are clean,
with no remaining processes, signals or cleanup errors. All copied input hashes
are identical before/after; frozen6,340-file source manifest remains unchanged
and independently recomputed. Three direct runtime sources match current bytes.

Final runner40958c49 pins the manifest99eea214 and existing v10 runner93c37b84,
policye41663b0 and ownership helper4f16b6c3 before execution. Pre-execution review
initially rejected the unpinned mutable selector manifest; this was corrected
before any tests ran. No test failure is fabricated from that review finding.

Targeted test Ruff passes135.524ms. Helper lint initially reports one unused
import (107.391ms, exit1), then passes after its removal89.654ms; final manifest
pin revision passes100.800ms. All three captures are retained. Independent
source, final pre-execution and runtime reviews PASS; root recomputed the
runtime counts and hashes independently as well.

## Boundaries and reproduction

Archived files are exact copies of executed private artifacts, bound by
`SHA256SUMS`. The archived runner documents the historical fixed private paths;
it is not a portable runner or an instruction to rerun completed exclusive
outputs. Private package:
`/private/tmp/localos-current-full-v10.BYwJr6/writable/fixtures-final-eUzlmH/`.

No application change, provider call, PostgreSQL access, Docker build, production
operation, push or deployment occurred. The restricted secondary OAuth test
was not read, copied, selected or executed. The old5516-node full aggregate
remains NONPASS until a fresh whole-scope run; integration, image206, load,
browser/CI/demo and final whole-diff gates remain separate open work.
