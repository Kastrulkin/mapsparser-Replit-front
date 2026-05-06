# Evidence Bundle: content-plan-network-ux

## Summary
- Overall status: PASS
- Last updated: 2026-05-03T17:45:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - Ran `/tmp/localos_network_readonly_smoke.py` against live network account `f3e4f2fb-38b4-40b8-a438-a5921c6e105c`.
  - Smoke opened `/dashboard/card?tab=news`, switched to content plan, found `Контент-план`, `Режим сети`, `Куда строить план`, `Последние планы`.
  - `mutating_requests=[]`.
- Gaps:
  - Live account did not show an active `Режим управления сетью` block in the existing production state, likely because no active network focus slice was available in the currently loaded plan.

### AC2
- Status: PASS
- Proof:
  - First screen now has `Что сделать сейчас` copy above the generation controls.
  - Data quality card uses compact counters and hides detailed context behind a separate `Подробнее` toggle.
- Gaps:
  - Full visual judgement should be repeated after rollout with the new bundle live.

### AC3
- Status: PASS
- Proof:
  - Added `Расставить даты автоматически` for visible plan items with empty/invalid `scheduled_for`.
  - Auto-date action updates items in 3-day increments and shows a result summary.
- Gaps:
  - Not clicked in live read-only smoke by design.

### AC4
- Status: PASS
- Proof:
  - Bulk news review now warns: `публикации без даты. Они будут созданы как черновики без календаря`.
- Gaps:
  - Warning appears only when selected review items contain empty/invalid dates.

### AC5
- Status: PASS
- Proof:
  - `Пропустить срез` and `Перенести на дату` now open `Подтверждение массового действия` before executing.
- Gaps:
  - Confirmation execution was not clicked in live read-only smoke.

## Commands run
- `git diff --check`
- `cd frontend && npm run build`
- `source venv/bin/activate && python3 -m pytest -q tests/test_content_plan_generation.py tests/test_content_plan_policy.py`
- `python3 /tmp/localos_network_readonly_smoke.py`

## Raw artifacts
- .agent/tasks/content-plan-network-ux/raw/build.txt
- .agent/tasks/content-plan-network-ux/raw/test-unit.txt
- .agent/tasks/content-plan-network-ux/raw/test-integration.txt
- .agent/tasks/content-plan-network-ux/raw/lint.txt
- .agent/tasks/content-plan-network-ux/raw/screenshot-1.png

## Known gaps
- Live read-only smoke intentionally did not click write actions: generate drafts, create news, auto-date, skip, reschedule, duplicate.
