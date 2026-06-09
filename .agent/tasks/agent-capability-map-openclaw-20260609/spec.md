# Task Spec: agent-capability-map-openclaw-20260609

## Metadata
- Task ID: agent-capability-map-openclaw-20260609
- Created: 2026-06-09T10:35:21+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 4: расширить build_agent_blueprint_orchestrator() до общей capability map через OpenClaw/ActionOrchestrator; проверить регистрацию OpenClaw/capability endpoints во Flask и устранить P0, если контракт документирован, но не подключен.

## Acceptance criteria
- AC1: `build_agent_blueprint_orchestrator()` uses a shared Stage 4 capability handler map, not a single `outreach.send_batch` handler.
- AC2: The map includes the requested Stage 4 capabilities and backward-compatible aliases.
- AC3: `/api/capabilities/*` and `/api/openclaw/*` execution/status/catalog/health routes are registered in Flask.
- AC4: OpenClaw M2M routes require `X-OpenClaw-Token` or Bearer token and use the same `ActionOrchestrator`.
- AC5: Communications compiler allowlist uses typed `communications.send_reminder` and `communications.send_offer`.
- AC6: Architecture docs record the registered capability surface and remaining safe-handler follow-ups.

## Constraints
- No production data changes.
- No schema migration in this stage.
- External send/publish/booking side effects remain request/draft only unless a separate approved domain integration exists.
- Keep old capability names working as aliases.

## Non-goals
- Full implementation of every historical OpenClaw ops/export endpoint beyond registered wrappers.
- Autonomous external sends or provider writes.
- Deploy.

## Verification plan
- Build/import: route-map import of `main`.
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: OpenClaw catalog token smoke via Flask test client.
- Lint: `git diff --check` and no added `as` usage in Stage 4 files.
- Manual checks: route map includes `/api/capabilities` and `/api/openclaw`.
