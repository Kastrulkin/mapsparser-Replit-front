# SEC-APIFY-TRACE-01 — safe service diagnostics and compatible status reader

Parent `c587b20f5f28187c1fed04323e6f6b118982282c`. P1 before production:
reachable `ProspectingService.run_business_by_map_url` passed raw URLs, actor
inputs, provider responses/errors and rejected candidate details to
`_append_debug_trace`. The append operation also reserialized every historic
raw event. Separately, `search_businesses` printed provider exception content
after a best-effort credential-pattern redactor. Arbitrary private values do
not need a recognized secret name to leak.

Likelihood depends on debug logging being enabled / actor failure and access
to artifacts/logs; high source and synthetic-test confidence, high possible
privacy impact. Small local patch; low functional blast radius and a deliberate
reduction in diagnostic detail. No current compromise or live exploit claimed.

## Implementation and consumer contract

The writer emits version2 events with ten source-defined stage names (unknown
input becomes `other`) and bounded value-free payload shapes. On a subsequent
append, prior entries retain only fixed stage names and validated ISO-looking
timestamp text; raw payloads, arbitrary keys/values and prior payload shapes
are not copied. Only the newest event retains a payload shape. The stage
timeline remains uncapped: this is not a global size/retention fix. Existing
files not appended during runtime remain unchanged; no cleanup was executed.

There is a real consumer: `parsing_networks._humanize_parse_error_message`
formerly read the rejected candidate's raw name/city/address from the trace.
For a version2 `identity_filtered` event it now returns a fixed actionable
Russian mismatch message before attempting legacy extraction. Genuine v1
traces, unrelated errors and absent-bundle behavior retain their prior contract.
The actor-failure console prints a fixed event and reraises the same exception.

The provider execution/result functions are untouched. Original run IDs,
items, actor input, run data and cost/usage metadata remain in memory and in
functional results for the worker. The fixed writer does not sanitize or
mutate those values; raw functional IPC is a different boundary.

## Reproduction, verification and independent review

`tests/test_apify_diagnostic_privacy.py` uses the actual service module and
an AST-extracted status helper; no runtime route/main registration. Synthetic
cases cover fresh/legacy payload persistence, arbitrary event names, disabled
and failed writes, every current call-site stage name, original actor failure,
v2 producer-to-reader status, explicit v2, v1 and unrelated/missing cases.
Global external-I/O guard is installed before pytest collection; conftest and
third-party plugin autoload are disabled, environment cleared. No provider,
browser or DB call is permitted. New actor-error test uses an uninitialized
service with a fake run method, not a real API client.

- `apify-diagnostic-red-20260921.json`:6failed/8passed in0.81s,
  1159.708ms captured; six causal privacy/reader failures, no harness error.
- `apify-diagnostic-green-20260921.json`: same14cases pass in0.52s/852.551ms.
- `apify-diagnostic-quality-20260921.json`:337.446ms; exact baseline source
  matches parent, same final tests/helper; five functional ASTs unchanged
  (business run, search run, start, fetch, normalization); scoped Ruff/compile.
- `apify-diagnostic-adjacent-20260921.json`:34passed in8.65s /9008.529ms,
  seven hashes. Includes the14new tests and20existing service/proxy/normalize
  tests, actual class with provider stubs. Named tmux session completed; an
  initial too-early artifact read failed, subsequent completed capture passed.
  No restart occurred and no evidence was overwritten.
- `parser-privacy-final-20260921.json`: combined86passes +4subtests in10.61s,
  10996.407ms;20source hashes reconciled by final quality269.823ms. Adds the
  previous49parser/worker units and3new legacy leaf cases to the34Apify tests.

Naive fragment-wide Ruff reported286 undefined names supplied through
`globals().update(_shared.runtime_namespace)`. The quality capture reproduces
the same286 diagnostic multiset/exit1 on parent and current fragment: **not**
a fragment lint pass. New tests and service scoped checks pass; inserted
reader code compiles. Git temp-directory warnings are retained separately.

Read-only independent review traced all producers/consumers, checked the
current source/test/helper hashes against GREEN, and approved the bounded fix.
It explicitly confirmed the reduced forensic detail and existing no-trace
fallback, not broad service/network integration or production readiness.

## Remaining risks

Missing/unreadable/legacy trace can still yield raw legacy mismatch text;
other returned/persisted exceptions, worker logs, raw functional IPC, retained
files and deployed code require separate work. No timestamp-semantic validation,
global artifact size limit, rotation, retention or historical deletion claim.
Native aggregate/restore, Docker image, demo/CI and full independent release
gates remain open. No production, DB/provider, Docker, cleanup, push or deploy.
