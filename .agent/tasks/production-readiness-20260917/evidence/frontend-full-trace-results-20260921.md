# Full frontend trace — 21 September

Parent `453eea52`; frozen application `99849935`. Diagnostic classification:
**NOT_REPRODUCED**, not FIX_PROVEN. No product, assertion, timeout or worker-cap
change was made. Earlier default-full v5 828/830 with two failures remains valid
historical evidence; capped v6 and isolated repeats never proved its cause.

## Full run and scope

`npm test -- --config <owned temporary config>` passes **830/830 in143 files**,
Vitest112.35 s / captured115.115 s, exit0 and no interruption. The temporary
config imports the unchanged frozen config, retaining React, aliases, jsdom,
setup and defaults. It only appends instrumentation/reporter and isolates Vite
cache under its owned temp directory. All5,720 tracked blobs/modes and seven
focused source/config/package hashes match before/after. Active/archived Node
network guard hashes match `0af671c1...b6c547`; bounded negative probe passes.

Four raw-hash-gated in-memory transforms instrument the two candidate tests,
LanguageContext and SEOKeywordsTab. They do not change assertions, promises,
timeouts or worker count. Exact-ID checks reject unrelated/drifted modules.
The installed Vitest reporter API and console batching were checked directly;
combined prefixed console frames are parsed separately. Logging is capped at
200 events, runtime900 s, disk5 GiB start/2 GiB live. Only successfully owned
temporary paths are cleaned, with cleanup failure rejected, not called success.
Pure transform/drift/config/reporter/framing controls, Ruff and diff check pass
in2.799 s. Independent pre-execution review PASS after correcting draft gaps.

Actual trace has37 events:27 runtime markers, three passing case results and
module/case lifecycle records. No invalid frame is reported. From each
test.active marker (different worker clocks must not be compared directly):

| Candidate | Provider render marker | Keyword render marker | Case duration |
| --- | ---: | ---: | ---: |
| Greek audience |165.90 ms |not applicable |992.62 ms |
| Turkish content plan |26.52 ms |not applicable |144.67 ms |
| Turkish SEO keywords |190.54 ms |431.58 ms |1,126.27 ms |

Markers occur during render, not an independent React commit/DOM measurement.
The unchanged test assertions separately confirm the expected DOM in this run.
Instrumentation can perturb timing, and host load/cache differ from prior runs:
112.35 s versus v5's199 s is **not** a performance improvement claim. Since no
failure occurred, neither delayed locale loading, effect scheduling nor order
contamination is established as the cause of the historical flake.

Stderr is not empty (10,236 characters). It retains jsdom unsupported navigation/
scrollTo notices and expected negative-path error logging from auth, membership,
request-race and ErrorBoundary tests. All830 cases pass; this does not assert
that every warning is harmless in production or that browser E2E is complete.

## Cleanup and next action

The exact generated config/setup/plugin/reporter/cache directory is removed;
copied inputs, raw output and structured events remain under the evidence
archive with10 SHA256 entries. No Docker, existing DB, provider, production,
push or deploy action is part of this frontend run. The concurrent PG package
was separately committed as453eea52 with normal hook/strict secrets scan PASS.

Independent runtime review PASS, including raw/events/manifest agreement,
source/guard and actual temp removal. Historical frontend
instability remains OPEN; do not raise timeouts or reduce parallelism and claim
a causal fix. Preserve this full-scope diagnostic and investigate a next actual
failure with its phase evidence. Continue unverified PG families and current-
source/backend/browser/security/performance/CI/demo/final gates. Backend accepted
slices remain2,687/5,481; frontend results are not added to that denominator.
