# Task Spec: agent-architecture-canon-20260609

## Metadata
- Task ID: agent-architecture-canon-20260609
- Created: 2026-06-09T09:07:20+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Этап 1. Инвентаризация и канон: зафиксировать LocalOS Agent Architecture v1, определить Agent/Persona/Blueprint/Compiled Workflow/Capability/Run/Approval/OpenClaw boundary, составить таблицу существующих блоков с решениями use/adapt/legacy/delete, закрепить правило communication agent как category blueprint.

## Acceptance criteria
- AC1: Created canonical `LocalOS Agent Architecture v1` document.
- AC2: Document explicitly defines `Agent`, `Persona`, `Blueprint`, `Compiled Workflow`, `Capability`, `Run`, `Approval`, and `OpenClaw` / `ActionOrchestrator`.
- AC3: Document includes an inventory table that assigns every discovered agent-related block to one of four states: `используется как есть`, `используется после адаптации`, `legacy wrapper`, `удалить после миграции`.
- AC4: Document states that communication agents are not a separate entity and must be represented as `AgentBlueprint.category = communications`.
- AC5: README links to the canonical document.

## Constraints
- Planning/documentation only; no runtime code or schema changes.
- Do not remove existing blocks during this stage.
- Do not imply unsupported autonomous external sends, provider writes, public MCP, or payments without human approval.

## Non-goals
- Implementing communication agents.
- Refactoring `AIAgents`, `AgentBlueprints`, OpenClaw, or UI routes.
- Production deployment.

## Verification plan
- Build: not applicable; documentation-only change.
- Unit tests: not applicable; no code changed.
- Integration tests: not applicable; no runtime changed.
- Lint: `git diff --check -- README.md docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`
- Manual checks:
  - `rg` required definitions in `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`
  - `rg` required inventory states in `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`
  - `rg` communications rule in `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`
  - `rg` README link to `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`
