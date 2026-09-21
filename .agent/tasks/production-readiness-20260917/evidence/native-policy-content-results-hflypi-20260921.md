# Policy/content batch and frontend flake investigation

Frozen source `99849935`, parent audit checkpoint `ea1a5036`, 21 September2026.
No product/test assertion changes for these runs. No production, existing DB,
provider send, Docker mutation, push or deployment.

## Backend: scoped PASS

The unchanged four-module batch ran sequentially under the existing default
guard and clean environment, without DATABASE_URL, TC mode or provider keys:

- `tests/test_founder_outreach_campaigns.py`:174
- `tests/test_legacy_agent_approval_policy.py`:69
- `tests/test_content_plan_generation.py`:67
- `tests/test_agent_template_validation_fixtures.py`:54

Actual364collected/364passed, zero errors/skips/xfails, exit0, empty stderr.
Pytest1.94s, capture2.490s, complete preflight/test/postcheck4.084s. Callbacks
contain364unique nodes in the exact allowed modules; per-module counts match.
All5720frozen tracked blobs/modes and installed default guard07d3... match
before/after. Independent runtime review checked raw results and support hashes.

The support change adds only a named pure-unit profile and multiple literal
targets to shared result helpers. The old200-node profile remains the default;
TC profiles, adapter, relay and runtime guard were not broadened. Pure controls
reject skips, foreign targets and count redistribution between allowed modules.
Ruff3files, legacy TC profile controls, unit controls and diff check pass
(262.1ms capture). Three captures and manifest are archived at
`native-unit-policy-content-hflypi-20260921/`.

Fresh cumulative backend count:573distinct passed/5481collected across seven
module slices, not a full aggregate.4908nodes remain unexecuted (85mapped PG
group and4823other nodes). Tests are evidence for frozen99849935 only.

## Frontend: NOT_REPRODUCED, not fixed

Two formerly failing modules were repeated five times under the unchanged
default Vitest configuration, with no `--maxWorkers` or test-timeout override:
`SEOKeywordsTab.i18n.test.tsx` and `ContentPage.i18n.test.tsx`.
Each raw capture reports exactly2files/3tests passed, exit0, no timeout/disk
stop and empty stderr. Total15test executions, only3distinct tests.
Outer durations:13.705s,5.703s,6.584s,5.970s,5.318s.

Tracked source5720/zero mismatches before/after; package, lock and Vitest config
hashes unchanged. Active Node guard bytes equal the archived previously tested
guard (`0af671c1a0302ec5f1357c5c25336044599ca771796ba219b4e6661521b6c547`).
Evidence is `frontend-flake-repeat-hflypi-20260921/`. The original repeat
launcher's exit code alone was insufficient: it gated only source integrity.
Acceptance here is based on independent inspection of all five raw test
outputs, not that launcher exit code. Any later helper-hardening verification
is separate from these unchanged historical captures. The later v2 helper
requires all five exact results and unchanged identity/config, returns nonzero
otherwise, and adds bounded owned-process cleanup. Five pure acceptance
controls pass; independent static review accepts the helper. It was not used
to rerun the five tests, and exceptional-process cleanup was not dynamically
exercised. `helper-provenance-v2.json` binds both helper versions honestly.

The full-default-worker v5 failure remains unresolved. Isolated green repeats
neither explain it nor show a fix; scheduling, load and suite interaction are
still hypotheses. No test assertion, product code, timer or worker override
was changed to obtain these results.

## Next

Continue remaining backend/PG/aggregate checks and the full-suite-only frontend
failure investigation. A parallel synthetic reproduction is examining the
still-open legacy-parser exception privacy boundary; it is a separate security
package, not implied fixed by these test runs. Security/browser/performance/
CI/whole-goal requirements and historical whole-goal FAIL remain open.
