# Task Spec: agents-version-diff-activate-rollback-phase4-20260526

## Metadata
- Task ID: agents-version-diff-activate-rollback-phase4-20260526
- Created: 2026-05-26
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md

## Original task statement
Phase 4: версии с diff / activate / rollback. Сделать видимым, чем новая версия отличается, какая версия активна, как откатиться и как запустить конкретную версию.

## Acceptance criteria
- AC1: API exposes active version for blueprint list/detail without schema migration.
- AC2: Version diff shows readable changed fields between versions.
- AC3: Feedback-created version becomes active and returns diff/event metadata.
- AC4: User can activate a version and rollback to an older version.
- AC5: New runs default to active version, and explicit `blueprint_version_id` still starts that specific version.
- AC6: `/dashboard/agents` shows active version, diff summary, activate/rollback, and run-version actions.
- AC7: Tests, lint, frontend build, deploy, and server smoke pass.

## Constraints
- No DB migration for this phase.
- Existing AgentBlueprint run/approval/send boundaries stay unchanged.
- Production data is touched only through self-cleaning smoke fixtures.

## Non-goals
- Full visual diff editor.
- Version branching/merge.
- New agent categories.
- Changing external dispatch policy.

## Verification plan
- Unit tests: `python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Lint: `scripts/lint_backend_baseline.sh`
- Build: `npm --prefix frontend run build`
- Deploy: `scripts/deploy_backend_src.sh`, `scripts/deploy_frontend_dist.sh --build`
- Integration smoke: `python /app/scripts/smoke_agent_blueprint_document_api.py` inside production app container.
- Browser sanity: open `/dashboard/agents` and verify bundle loads/redirects cleanly.
