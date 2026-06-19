# Task Spec: social-posting-loop-20260619

## Metadata
- Task ID: social-posting-loop-20260619
- Created: 2026-06-19T10:07:28+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Автономная разработка: реализовать дальнейший план по постам в соцсети для LocalOS Maps + Social Posting Agent: Telegram/VK/Google/supervised/metrics/UX publishing loop

## Acceptance criteria
- AC1: Approved VK social posts publish through native VK API when encrypted account binding contains `access_token` and `group_id`/`owner_id`; missing credentials become recoverable manual status.
- AC2: Approved Google Business posts use the existing Google publish worker boundary when dependencies/account binding are present; missing dependency/account/permission becomes recoverable manual status.
- AC3: Manual attribution events for leads/inquiries/comments/shares/clicks update social post metrics and keep next-plan ranking focused on leads/inquiries.
- AC4: Content plan UI exposes channel filtering, quick lead/inquiry attribution, and clearer supervised task instructions for Yandex/2GIS.
- AC5: Existing approval invariant remains: no external publish without explicit approval.

## Constraints
- LocalOS content plan remains source of truth.
- No production data mutation without approval.
- No schema change in this phase.
- Browser automation for Yandex/2GIS remains supervised/manual, not hidden autopublish.
- Keep existing design system and content-plan screen; do not create a separate scheduler product.

## Non-goals
- No Meta Graph real publish activation until permissions and account binding are verified.
- No automatic rewrite of future content plans without human approval.
- No production browser automation click-through for Yandex/2GIS.

## Verification plan
- Build: `npm run build` in `frontend`.
- Unit tests: social post service/API route tests and external accounts route contract.
- Integration tests: deploy smoke after commit/push.
- Lint: targeted compile via `py_compile`.
- Manual checks: production `docker compose ps`, app logs, `curl -I`, DB revision, social posts auth guard.
