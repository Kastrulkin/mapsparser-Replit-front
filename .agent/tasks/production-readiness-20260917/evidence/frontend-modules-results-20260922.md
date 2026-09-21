# Frontend module boundaries — 22 September

## Scope and cause

`ARCH-FRONTEND-RATCHET-01` is a local maintainability/CI finding, not a newly
discovered user-facing malfunction. The existing size gate failed on
`AgentBlueprintsWorkspace.tsx` (2,260 lines versus 2,087); `employee.tsx` also
exceeded its separate limit (2,237 versus 2,233). Limits were not increased.

The selected user's flow remains configuring an AI employee's connections,
reviewing its work and choosing the next action. No screen, wording, approval,
request payload or workflow is redesigned. Seven connection handlers move to
`agents/integration-actions.ts`; all 249 original handler lines are byte-for-byte
equal to the corresponding block in the new module. The factory is called on
every render, preserving the previous closure lifetime, without moving hooks,
state or effects. StatusBadge and AgentMiniMetric move to a 16-line component
module; the previous AgentMiniMetric export remains available.

Final sizes: workspace 2,024; employee 2,225; integration actions 300 lines.
This removes the two gate violations, not all large-module debt. No measured
latency improvement is claimed.

## Verification

- Original size gate: 1 failed / 1 passed, 384.832 ms capture.
- Current size gate plus generic-agent contracts: 58 passed, 1,272.014 ms.
- Final app/node TypeScript: exit 0, 42,545.044 ms.
- Full frontend lint: exit 0, 15,184.353 ms; one pre-existing `any` warning in
  `src/lib/auth_new.ts:115`, within the repository's existing warning budget.
- Final targeted unit tests: 27/27 across four files, 10,529.839 ms capture.
  Includes request identity/stale-result integrity, schedule hydration, existing
  employee rendering and ten new connection-action cases (seven handlers,
  no-selection admission, saved-access prerequisite, error recovery and ordering).
- Full frontend unit run: 840/840 tests in 144/144 files, exit 0,
  129,452.346 ms capture / 127.16 s Vitest; no skips, timeout or output truncation.
- Final dashboard and public Vite builds: exit 0, 25,793.071 ms. Four existing
  third-party PURE-comment annotation warnings were emitted; no build errors.
- Independent source review accepted the extraction; an unused statusTone import
  identified by review was removed. Final independent runtime/package review PASS:
  all 16 artifact hashes, five source hashes, counts and stated limitations checked.

The first new error-path test incorrectly expected fallback copy instead of the
existing normalizer's Error.message. That attempt was 26 passed / 1 failed. The
test now checks the actual established error contract; production error handling
was not altered. Original failure and test source are retained. First-attempt
TypeScript, scoped ESLint and both Vite builds passed, but final evidence is
reported separately rather than silently replacing the failed test attempt.

## Isolation and source identity

Fresh frontend snapshot is `git archive b12cfcb2 frontend` plus exactly the five
owned edited/new source files. Installed dependencies are an APFS clone of the
existing workspace node_modules, not a fresh installation or a clean-install
reproducibility claim. Package lock SHA-256:
`a4e1362910fe02f286e950840fd79141fd411533b7743aa79f8c1a450ddece8b`.

Named tmux sessions run with an empty inherited environment, task-owned HOME and
TMPDIR, macOS network denial inherited by children, no user-directory reads,
and writes confined to the owned snapshot. Existing Node network guard additionally
blocks application requests. The original workspace and historical snapshots are
not build targets. Snapshot: `/private/tmp/localos-front-ratchet.FLczSS`.

Final owned source SHA-256 values, ordered workspace / employee / primitives /
integration-actions / new tests:

```
e4d0c44bc74cd638cbaa79093d54df0fcd33ffa9452f631f87fc6752455cf41a
a389e6dd53e570ae85c864d1543b9115e282637a90d12708e1c6895425e3972b
4484805878986f85f073457c60b8fee350ac47d1840749369e2c19152dbbb802
341cb5a2ab42d2dee392c8115dd339be7808c6dcf73fd4e83e3865c397aa4f34
202c7bbe621b69d90bd96d5d3eff7eae8c69e706fca28e0fd51ef251c83dad6c
```

Foreign tracked diff SHA remains `40afa0141e5fe1b9fe9d18ee651ba61e19a27367158d71984f5a90a4d2a4c6d1`;
all thirteen foreign paths are preserved. No push, deploy, real integration call,
database mutation or repeated cleanup. Browser/live behavior and the whole
production-readiness objective remain outside this local extraction verdict.

Raw captures and exact execution scripts/policy are archived in
`frontend-modules-20260922/` alongside a content hash manifest. This is one
successful full frontend run, not proof that historical intermittent failures
cannot recur. The previous whole-backend offline NONPASS is not recalculated.
