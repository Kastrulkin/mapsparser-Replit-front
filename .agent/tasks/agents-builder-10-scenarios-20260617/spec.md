# Task Spec: agents-builder-10-scenarios-20260617

## Metadata
- Task ID: agents-builder-10-scenarios-20260617
- Created: 2026-06-17T13:15:14+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Прогнать 10 пользовательских сценариев создания агентов, исправить неверное понимание LocalOS и подтвердить проверками

## Acceptance criteria
- AC1: All 10 user-request scenarios are classified into a plausible LocalOS agent category or custom integration workflow.
- AC2: The builder must not ask cross-domain questions, especially lead/prospectingleads questions for non-outreach scenarios.
- AC3: Scheduled Telegram scenarios use the Telegram delivery/connection flow instead of outreach or generic source questions.
- AC4: Google Sheets and finance scenarios keep their required source connection questions when the user did not provide a concrete table.
- AC5: Regression tests and frontend build pass.

## Constraints
- Do not modify production data.
- Do not deploy unrelated dirty files.
- Keep external sends behind LocalOS connection/approval flow.

## Non-goals
- Implementing actual production execution of the newly described agents.
- Adding new database schema.
- Changing unrelated agent UI layout.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `venv/bin/python -m pytest tests/test_agent_blueprint_layer.py -q`
- Scenario check: run `build_agent_builder_state` for the 10 provided prompts and inspect category, sources, setup status, and questions.
