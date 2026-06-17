# Task Spec: agents-builder-fourth-10-browser-20260617

## Metadata
- Task ID: agents-builder-fourth-10-browser-20260617
- Created: 2026-06-17T19:15:50+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Browser-use проверить четвертый набор 10 сценариев конструктора пользовательских агентов, найти ошибки понимания/UX, исправить, протестировать и задеплоить

## Acceptance criteria
- AC1: All 10 new user prompts are exercised through the browser flow on `/dashboard/agents`.
- AC2: The builder no longer maps these prompts to unrelated old domains such as finance expenses, photo quality, lead search, or cancellation-risk agents.
- AC3: The visible "Что понял LocalOS" summary names the expected data sources and expected result/control for each scenario in user-facing terms.
- AC4: Existing agent-builder behavior remains covered by the full `tests/test_agent_blueprint_layer.py` suite and frontend production build succeeds.
- AC5: The fixed backend services and frontend dist are deployed to production and the app answers HTTP 200 after restart.

## Constraints
- Do not create real agents while testing; stop at the builder understanding/preview flow.
- Do not modify production data.
- Keep unrelated dirty worktree files out of this task commit.

## Non-goals
- Implementing real inventory, staff schedule, chat, or revenue integrations.
- Redesigning the whole agents screen beyond wording/mapping fixes needed by this scenario pack.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- Integration tests: browser-use on production `/dashboard/agents` for the 10 prompts.
- Lint: not run separately; this change is covered by targeted tests and production frontend build.
- Manual checks: production partial deploy, `docker compose ps`, `curl -I http://localhost:8000`, app logs after restart.
