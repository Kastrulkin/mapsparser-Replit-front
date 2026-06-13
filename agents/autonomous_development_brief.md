# Autonomous Development Brief (Generic)

This brief defines default behavior when the trigger phrase `Автономная разработка` is used.

## 1) Goal Contract
- Deliver a working result, not partial progress.
- Keep iterating until Definition of Done (DoD) is met or a hard blocker is reached.
- Prefer small, reversible changes with fast feedback loops.

## 2) Default Iteration Loop
1. Confirm target behavior from task text.
2. Pick one concrete hypothesis for current failure/gap.
3. Implement minimal change for this hypothesis.
4. Run the smallest relevant checks first, then broader checks.
5. Evaluate result against DoD and logs.
6. Keep/discard, record decision, and move to next hypothesis.
7. Repeat until success criteria are met.

## 3) Experiment Discipline
- One hypothesis per iteration.
- One measurable result per iteration.
- Keep concise iteration notes:
  - hypothesis
  - change
  - result
  - keep/discard
- Optimize for reliability and reproducibility, not single-run success.

## 4) Safety and Quality Guards
- Validate outputs before persisting or exposing in UI/API.
- Do not overwrite known-good state with low-confidence results.
- Add machine-readable reason codes for rejected/failed operations.
- Isolate failed units where possible so one failure does not stop whole flow.

## 5) Verification Standard (Server)
Run in this order:
1) `cd /opt/seo-app && docker compose ps`
2) `cd /opt/seo-app && docker compose logs --since 15m app`
3) `cd /opt/seo-app && docker compose logs --since 15m worker`
4) `cd /opt/seo-app && curl -I http://localhost:8000`
5) Task-specific endpoint/UI/job checks

For frontend runtime errors:
- correlate browser console stack with app/worker logs.

## 6) Deployment Rules
- Prefer partial deploys.
- Frontend-only changes: update `frontend/dist`.
- Backend-only changes: sync `src/` and restart only needed services (`app`, `worker`).
- Avoid full rebuild unless required by the fix.

## 7) Database and Data Safety
- No production data changes without explicit user approval.
- Schema changes only via Alembic migrations.
- Before production schema changes: take a backup.
- Prefer idempotent migration patterns (`IF EXISTS`/`IF NOT EXISTS`).

## 8) Hard Blockers
Stop and ask user only when:
- action is destructive or irreversible
- risky production schema/data operation is required
- required access is missing
- multiple valid business behaviors require product choice

## 9) Completion Criteria
- DoD is met.
- Relevant checks pass.
- No new critical regressions in adjacent flows.
- Final report includes:
  - what changed
  - what was verified
  - residual risks (if any)

## 9.1) Agent/Runtime Task DoD Addendum
For tasks that change agent runtime, orchestrator behavior, Agent API, tools/capabilities, approvals, MCP/external connectors, prompt/context assembly, compaction, or supervised outreach:

- Harness boundary is documented: what the model proposes and what LocalOS code enforces.
- Tool/capability contract is narrow and typed: input, output, risk class, side effects, permission policy, timeout, retry behavior, audit event.
- Risky actions keep draft and commit separated.
- Approval is enforced outside prompt text for publishing, external sends, payments, destructive changes, credential changes, and third-party actions.
- Every tool/capability call returns a structured observation, including denial, timeout, validation error, and `pending_human`.
- Agent state that must survive resume/compaction is stored outside prompt context or has a documented rehydration path.
- Stop conditions and budgets are explicit for long-running or batch work.
- Trace/audit evidence exists for tool calls, permission decisions, approvals, failures, and final status.
- Evals or targeted tests cover at least one happy path and one safety/failure path, such as approval bypass, invalid arguments, missing scope, malformed tool result, or budget exhaustion.
- Public docs do not imply unsupported MCP, provider write support, autonomous publishing/sending/payment, or direct external-system action.

## 9.2) Supergoal-Inspired Goal Execution
For large, multi-phase product or engineering tasks, use a goal-first workflow inspired by Supergoal, while keeping the repo-local proof loop as the canonical execution mechanism.

### Goal First
- Preserve the user's original end-state as the primary objective.
- Do not shrink the goal to the easiest shippable subset.
- Every phase must move the current state measurably closer to the original goal.
- If the goal is broad, decompose it; do not replace it.

### Recon Before Phase Planning
Before implementing a large task:
- read canonical repo guidance;
- inspect current implementation and docs;
- identify existing reusable blocks;
- identify risky areas, migrations, external services, UI surfaces, and deployment impact.

Output a short recon summary before the first substantial edit.

### Adaptive Phases
- Choose the number of phases from the work itself; do not force a fixed count.
- Each phase must have:
  - purpose;
  - deliverables;
  - measurable acceptance criteria;
  - required checks;
  - evidence needed for completion.
- The last phase must be polish, hardening, or audit when the task affects product UX, runtime behavior, integrations, billing, approvals, or data.

### Preflight
Before executing a large phase:
- run the smallest baseline checks that prove the current repo/server state is usable;
- identify already-broken checks separately from changes introduced by the current task;
- do not let a broken baseline create fake failure loops.

For LocalOS production/server work, preflight must respect:
- Docker/Postgres runtime;
- `/opt/seo-app` server cwd;
- backup before schema changes;
- partial deploy preference.

### Phase Verification
A phase is not done until:
- implementation is present in the current worktree;
- relevant commands pass or failures are explained as pre-existing/unrelated;
- acceptance criteria are checked independently;
- evidence is recorded in the proof bundle or final report.

Do not rely on builder narrative as proof.

### Recovery Policy
When a phase fails:
- first failure: diagnose and retry with a focused hypothesis;
- second failure: write a minimal fix spec and execute it;
- third repeated failure on the same blocker: stop with a handoff summary unless another safe path exists.

Do not loop indefinitely.

### Final Audit
Before final sign-off:
- re-read the original goal and acceptance criteria;
- verify every explicit requirement against current files, command output, runtime behavior, or deployed state;
- re-run aggregated mandatory checks where practical;
- check that deliverables exist in the working tree, not only in the plan;
- list residual risks honestly.

Only claim completion when the audit proves the original goal is satisfied.

### Memory / Learning Writeback
At the end of a large task, capture non-obvious learnings:
- project constraints discovered;
- commands that worked or failed;
- deployment quirks;
- user product preferences;
- reusable implementation patterns.

Store them in the task proof artifacts or project docs when they will help future work.

### Product-Agent Tasks Addendum
For LocalOS AI-agent work, every phase must preserve the product model:
- LocalOS is the product/policy/billing/audit envelope.
- OpenClaw is an execution/runtime boundary, not the product source of truth.
- Compiled workflow is runtime truth, not free-form prompt text.
- Risky external actions require approval outside prompt text.
- Required connectors/bindings must be explicit before activation.
- Safe preview must happen before active execution.
- Run history, action ledger, costs, errors, and recovery actions must be observable.

## 10) Task Template
Use this template when starting autonomous work:

```

## 11) Repo Task Proof Loop Integration (Default in autonomous mode)
- Trigger `Автономная разработка` implies proof-loop workflow by default.
- Start rule:
  - if no task bundle exists: `scripts/proof_loop.sh init <TASK_ID> "<task text>"`
  - if bundle exists: continue current `<TASK_ID>` without re-init
- During execution, keep artifacts in:
  - `.agent/tasks/<TASK_ID>/`
- Minimum proof discipline before final sign-off:
  1) `scripts/proof_loop.sh validate <TASK_ID>`
  2) `scripts/proof_loop.sh status <TASK_ID>`
  3) fresh verifier pass (separate from implementer role)

Suggested TASK_ID format:
- `<area>-<goal>-<yyyymmdd>`

## 12) Autonomous Control Phrases
- `Статус автономной разработки`
  - execute: `scripts/proof_loop.sh status <TASK_ID>`
  - report current state + next action
- `Проверка автономной разработки`
  - execute: `scripts/proof_loop.sh validate <TASK_ID>`
  - report valid/invalid + concrete errors
Автономная разработка

Цель:
<target behavior>

Контекст:
<route/api/entity identifiers/log refs>

DoD:
1) ...
2) ...
3) ...

Проверка:
- команды:
- ручной сценарий:

Ограничения:
- нельзя:
- можно:
- деплой: да/нет
```
