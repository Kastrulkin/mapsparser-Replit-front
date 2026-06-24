# Task Spec: agents-custom-create-reviews-telegram-20260616

## Metadata
- Task ID: agents-custom-create-reviews-telegram-20260616
- Created: 2026-06-16T15:13:03+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Попробовать создать кастомного агента: проверяет новые отзывы компании, генерирует ответ и отправляет отзыв и ответ в Telegram; найденные ошибки исправлять автономно.

## Acceptance criteria
- AC1: A user can create a custom agent for checking new company reviews, drafting a reply, and sending the review plus draft to Telegram without automatic publication.
- AC2: If required connection/provider choices are needed during creation, they are visible in the main builder flow and do not trap the user in hidden details.
- AC3: Created-agent overview uses product language in Russian and does not expose internal terms such as OpenClaw, Boundary, provider route, preflight, Preview run, or Production run.

## Constraints
- Do not approve or execute external Telegram/send/publish actions without explicit human approval.
- Deploy frontend-only changes through the standard frontend dist deploy path.

## Non-goals
- Do not accept the pending human decision created by the preview.
- Do not change production data except the user-requested test agent creation.

## Verification plan
- Build: `npm run build:all` in `frontend/`.
- Unit tests: not applicable for this narrow UI flow.
- Integration tests: production smoke via `/dashboard/agents`.
- Lint: covered by production build/type transform for this touched frontend bundle.
- Manual checks: browser creation flow, preview run, pending human decision, console errors.
