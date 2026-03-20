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

## 10) Task Template
Use this template when starting autonomous work:

```
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
