# Task Spec: agents-builder-40-browser-regression-20260618

## Metadata
- Task ID: agents-builder-40-browser-regression-20260618
- Created: 2026-06-18T05:44:47+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Повторно browser-use прогнать все прошлые 40 сценариев создания пользовательских агентов, исправить найденные ошибки, проверить и задеплоить

## Acceptance criteria
- AC1: Recover the previous 40 agent-builder scenarios and run them through the browser create-agent flow.
- AC2: No scenario maps to an obviously wrong domain such as lead search, finance expenses, photo quality, or cancellation risk unless that is the scenario itself.
- AC3: When a user edits the request after a preview is shown, the UI must not present the old preview as current or show duplicate disabled primary buttons.
- AC4: Automated checks pass after any fix.
- AC5: Production is updated and responds successfully after deploy.

## Constraints
- Browser-use must imitate the user path: open `/dashboard/agents`, click create, type prompts, click/update understanding, read visible summary.
- Do not create real agents; stop at preview/understanding.
- Do not touch unrelated dirty worktree files.

## Non-goals
- Implement real integrations for the 40 scenario domains.
- Redesign the whole agents screen.

## Verification plan
- Build: `npm --prefix frontend run build`
- Unit tests: `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- Integration tests: browser-use full 40-scenario live run on production.
- Lint: no separate lint command; covered by TypeScript build and focused tests.
- Manual checks: stale-preview guard in browser; production `docker compose ps`; `curl -I http://localhost:8000`.
