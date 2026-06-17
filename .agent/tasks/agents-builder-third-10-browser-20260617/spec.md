# Task Spec: agents-builder-third-10-browser-20260617

## Metadata
- Task ID: agents-builder-third-10-browser-20260617
- Created: 2026-06-17T17:35:14+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Browser-use проверить третий набор 10 сценариев конструктора пользовательских агентов, найти ошибки понимания/UX, исправить, протестировать и задеплоить

## Acceptance criteria
- AC1: All 10 supplied custom-agent scenarios can be entered through `/dashboard/agents` without cross-domain misunderstanding such as leads, generic services, review replies, or finance-only output where it does not belong.
- AC2: The builder preview uses user-facing source/result labels for newly recognized domains: photos, competitors, WhatsApp/customer questions, team tasks, seasonality, posts, schedule, business cards.
- AC3: Regression coverage exists for the 10 scenarios and previous agent-builder scenarios still pass.
- AC4: Changes are deployed to `localos.pro` and verified with browser-use on the live page.

## Constraints
- Do not create real production agents during browser testing.
- Do not modify production data except deploying code/static assets.
- Keep unrelated dirty workspace changes untouched.

## Non-goals
- Full redesign of the agent-builder wizard.
- Cleanup of duplicate source labels such as `отзывы компании, отзывы`.
- Changes to real integration configuration or Telegram/WhatsApp accounts.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q -k "agent_builder"`
- Integration tests: `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- Deploy checks: server `docker compose ps`, restart `app worker`, `curl -I http://localhost:8000`
- Manual checks: browser-use on live `/dashboard/agents` for all 10 prompts without creating agents
