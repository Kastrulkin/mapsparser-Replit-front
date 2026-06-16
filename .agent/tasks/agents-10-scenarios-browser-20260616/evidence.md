# Evidence Bundle: agents-10-scenarios-browser-20260616

## Summary
- Overall status: PASS WITH PRODUCT NOTE
- Last updated: 2026-06-16T20:25:30+03:00
- Scope: `/dashboard/agents` user-flow smoke in the production browser for custom agent creation, safety wording, delete/remove behavior, pending decisions, and visible technical terminology.

## Acceptance Criteria Evidence

### AC1: Incomplete request asks clear questions
- Status: PASS
- Proof: Browser scenario "ТЕСТ 04. Хочу агента для отзывов" showed "Сейчас нужно", a concrete clarifying question, reply controls, understood task, data, result, and manual-control summary.

### AC2: Dangerous external action requires human control
- Status: PASS
- Proof: Browser scenario asking to publish review replies without confirmation was translated into drafts and "Ручное подтверждение перед финальным использованием и любым внешним действием".

### AC3: UI does not leak internal terms in visible Russian interface
- Status: PASS
- Proof: Final browser smoke checked visible text for `inside_localos_policy`, `localos_managed_boundary`, `preflight_only`, `approval_required`, `provider route`, `policy envelope`, `OpenClaw`, `preview run`, `safe тест`, `available`, `pending`, `review`; none were found.

### AC4: Remove from list has explicit confirmation and cancel path
- Status: PASS
- Proof: Final browser smoke opened "Убрать агента из списка?" dialog and verified text saying history/results remain. Clicking "Отмена" kept the agent in the list.
- Product note: Before the fix, the old `window.confirm` flow did not surface correctly in the in-app browser and one test agent (`ТЕСТ 01 FINAL`) was removed from the list while reproducing the bug.

### AC5: Pending manual decision is inspectable without external side effects
- Status: PASS
- Proof: Browser opened the remaining agent with "Нужно решение"; manual-control/journal view displayed the pending decision state. No approve/reject action was taken.

## Fixes Applied
- Added user-facing cleanup for post-create handoff, connection plans, provider route summaries, activation blockers, preview summaries, run review setup, status badges, and journal summaries.
- Added translations/normalization for `safe preview`, `preview run`, `schedule.daily`, `available`, `pending`, `review`, `binding`, `inside_localos_policy`, `preflight_only`, `approval_required`, and underscore-separated state fragments.
- Replaced native `window.confirm` removal with an in-app confirmation dialog with explicit cancel and "history/results remain" language.

## Commands Run
- `npm run build:all` from `frontend/` after each patch; all successful.
- `scripts/deploy_frontend_dist.sh` in tmux after each successful frontend build.
- Production browser smoke on `https://localos.pro/dashboard/agents`.

## Final Production Verification
- Live bundle: `/assets/index-Dp_g_ezf.js`
- Final browser smoke: no caught internal terms, delete confirmation ok, no browser console errors, page showed `1 всего`.

## Known Gaps
- Full creation of additional Google Sheets/order-check test agents was not completed after discovering and fixing the delete-confirmation bug, to avoid further production data churn and credit spend.
- Existing real pending decision was inspected only; it was not approved or rejected.
