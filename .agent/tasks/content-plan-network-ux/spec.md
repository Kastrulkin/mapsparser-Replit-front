# Task Spec: content-plan-network-ux

## Metadata
- Task ID: content-plan-network-ux
- Created: 2026-05-03T17:07:55+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Network read-only smoke, simplify content plan first screen, add auto-date recovery, review warnings, bulk confirmations, and network operating UX

## Acceptance criteria
- AC1: Real network content-plan read-only smoke is completed without mutating requests.
- AC2: Content-plan first screen is more operational: primary action is clearer and detailed context/settings are tucked behind controls.
- AC3: Old or broken plan items without dates can be repaired through a soft auto-date action.
- AC4: Bulk news creation warns about items without dates before confirming.
- AC5: Bulk skip and move-to-date actions use an in-page review confirmation before writing.

## Constraints
- Do not mutate production data during read-only smoke.
- Keep implementation frontend-only unless backend changes are strictly required.
- Do not introduce a CMS or new dependency.

## Non-goals
- Do not change content generation backend semantics.
- Do not deploy database migrations.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: `python3 -m pytest -q tests/test_content_plan_generation.py tests/test_content_plan_policy.py`.
- Lint: `git diff --check`.
- Manual checks: Playwright read-only smoke on `https://localos.pro/dashboard/card?tab=news` with network account selected.
