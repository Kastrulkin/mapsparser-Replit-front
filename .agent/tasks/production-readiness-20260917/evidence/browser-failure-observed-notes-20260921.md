# Browser failing-request observation

Scope: `TEST-BROWSER-FAILURE-OBSERVED-01` only. These are isolated loopback
Vite/Playwright tests; they do not contact production, Docker, PostgreSQL or a
Telegram provider.

`browser-failure-observed-green-20260921.json` records the scoped shared-venv
command passing two tests. The guided-tour route recorder now requires exactly
two `PUT /guided-tours/roga-i-kopyta-v1/progress` requests. The Telegram Mini
App recorder now requires exactly one `POST /operator/chat` request before
accepting the generic malformed-response copy.

`browser-failure-observed-guided-tour-mutant-red-20260921.json` is a causal
negative control in a private `/private/tmp` worktree at `f90241b9`: only that
copy of `GuidedTourProvider.tsx` replaced the `moveTo` persistence call with
`const saved = true`. The UI still reached step 3 and retained local progress,
but the new assertion saw one PUT rather than two and failed. The temporary
worktree was removed after capture; no source in the main workspace changed.

The mutant capture has `stdout_truncated=true` (and `stderr_truncated=false`),
so it is not evidence of a complete untruncated test log. Its retained failing
assertion is sufficient for this narrow control: it reports one observed
`PUT /guided-tours/roga-i-kopyta-v1/progress` where the test requires two.
The private worktree used source
`GuidedTourProvider.tsx` from `f90241b9` with SHA-256
`55e970dfd34205be6acf0f16332df119c5789d1123b20bf00eee84cec1089162`.
Its only source substitution was:

```ts
const saved = await persistProgressSafely(nextStatus, nextStep, nextCompletedSteps);
```

to:

```ts
const saved = true;
```

The current owned test SHA-256 values are
`a2e8a763f12bce88da03fc44112d77b1b5bf03003d76f5b58deb7640e1cfe35e`
for `test_guided_tour_transient_gateway_error.py` and
`d37d58261f2f6e300ca8d60c5d3db310aa4500378e8577e82c8dda98a3178b52`
for `test_telegram_mini_app_operator_error.py`.

The final guided-tour version replaces its fixed 100 ms delay with two bounded
five-second Playwright `expect_response` waits: the start action must receive
the first exact progress PUT with status 200, and the next action must receive
the second exact progress PUT with status 502. The exact two-request recorder
and all existing UI, local-progress and error-copy assertions remain. The
response-wait two-test run and Ruff capture are
`browser-failure-observed-final-green-20260921.json` and
`browser-failure-observed-final-ruff-20260921.json`. Those two captures bind to
guided-tour hash `0210e56812b4e185e20cd3fe9edb9da214a1b5ede67bb2e2951cad54204f6692`.
The final cleanup removed optional context-manager bindings and redundant
status assertions; each status remains mandatory in its response predicate.
The post-cleanup `browser-failure-observed-final-v2-green-20260921.json`
records 2/2 tests passing in 19.70 seconds for the current test hashes above.
Ruff and `git diff --check` also passed after cleanup. Independent review
accepted the final test logic and preserved assertions.

The red mutant capture predates this response-wait refinement and therefore
binds exactly to the earlier guided-tour test hash
`b466305438d10a66e0aa1ff87cb165fcad4b5485e3806206c292b5f11a60ae1c`, not
the current hash. The retained failure demonstrates that the exact recorder
catches one PUT instead of two, but it is not an independently rerun
source-mutation proof of the final response-wait version. Because the private
worktree was removed, the reported one-line mutation and source hash cannot
be independently reverified from that worktree; its source provenance remains
builder-reported rather than an archived mutated-source artifact.

Two retained baseline captures explain environment selection: system Python's
Playwright 1.53 requested a deleted Chromium 1179 cache, while the repository
`venv` Playwright 1.58 uses the already present browser cache. The first venv
attempt also had an intermittent Vite loopback readiness timeout even though
Vite logged ready. No dependency or browser download was performed. The final
venv run passed.
