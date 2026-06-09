# Task Spec: agents-migration-cockpit-20260609

## Metadata
- Task ID: agents-migration-cockpit-20260609
- Created: 2026-06-09T13:08:59+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Полная migration/cleanup старых AIAgents и legacy ai_agent_* настроек плюс UI-polish: Мои агенты как product cockpit, versions/diff/learning history, понятные approval reasons, ясные activate/rollback controls.

## Acceptance criteria
- AC1: Legacy AIAgents can be migrated into persona/voice-backed blueprints through an idempotent, non-destructive apply path.
- AC2: Deprecated business fields `ai_agent_enabled`, `ai_agent_tone`, `ai_agent_restrictions`, `ai_agents_config`, and `ai_agent_id` are marked as migration sources, and runtime gates prefer active `agent_blueprints`.
- AC3: `AIAgents.workflow` is no longer runtime truth for chat/sandbox execution; it is exposed only as deprecated migration context.
- AC4: Legacy UI/API entrypoints that should not be product routes are removed from the product/admin cockpit path or redirected to `/dashboard/agents`.
- AC5: `/dashboard/agents` is polished into a product cockpit with migration health, learning history, version/diff surfaces, clearer activate/rollback actions, and plain-language approval reasons.
- AC6: Canonical docs and OpenClaw contract describe the unified architecture and cleanup rules.
- AC7: Focused backend/frontend checks pass.

## Constraints
- Do not delete production data or drop columns without Alembic migration, backup policy, and proof that UI/API/server flows no longer read the field.
- Keep migration apply non-destructive and idempotent.
- Preserve existing chat/persona rows as voice/persona data until a later physical cleanup is safe.

## Non-goals
- Physical database column drops for `Businesses.ai_agent_*`.
- Production data mutation without an explicit backup/apply run.
- Removing historical `AIAgentConversations` or `AIAgentMessages`.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: deploy smoke after push/deploy.
- Lint: Python compile check for touched backend modules.
- Manual checks: source grep for legacy UI imports, `WHERE ai_agent_enabled = 1`, and legacy workflow runtime markers.
