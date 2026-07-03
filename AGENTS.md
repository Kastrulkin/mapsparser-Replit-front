# Project Agent Rules (Canonical)

## 0. Mandatory Working Directory
- On server, run **all commands** from `/opt/seo-app` unless explicitly stated otherwise.
- Never assume current directory on server.
- Always start every server command block with:
  - `cd /opt/seo-app`
- This rule applies to `docker compose`, `docker`, `curl`, `grep`, `psql`, `python`, and any other server command.

This file is the canonical instruction set for AI agents in this repository.

## 1. Source of Truth
- Always read `README.md` first.
- Runtime stack is Docker + Docker Compose + PostgreSQL.
- SQLite is legacy-only for one-off migration/debug scripts; do not treat it as runtime DB.

## 2. Environments
- Local workspace path: `/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре`
- Server path: `/opt/seo-app`
- Primary domain used in checks: `localos.pro`

## 3. Deployment Policy
- Prefer partial updates; avoid full rebuild when not needed.
- Frontend-only changes: build locally and sync `frontend/dist` into `app` container.
- Backend-only changes: sync `src/` (and migrations when needed) into `app`/`worker`, then restart only affected services.
- Use `docker compose restart app worker` instead of restarting all containers.
- Canonical backend source path on server is `/opt/seo-app/src`.
- Do not copy Python runtime files into `/opt/seo-app/*.py` unless the file actually lives in the repository root.
- When verifying a hotfix, check the live file in container (`/app/src/...`), not only the host copy.

## 4. Database Safety
- Never modify production data without explicit user approval.
- Before schema changes on server: create DB backup.
- Schema changes only through Alembic in `alembic_migrations/versions`.
- Migration scripts must be idempotent where possible (`IF EXISTS`/`IF NOT EXISTS`).

## 5. Verification Standard
- Validate in this order:
  1) `docker compose ps`
  2) `docker compose logs --since ... app`
  3) `curl -I http://localhost:8000`
  4) targeted endpoint checks for changed feature
- For frontend runtime errors, prioritize browser console stack + app logs.

## 6. Documentation Structure
- `AGENTS.md` is the canonical rulebook for Codex and other AI agents in this repository.
- Product UI and UX rules are in `DESIGN.md`; read it before changing dashboard, cockpit, builder, form, approval, run-history, or agent-management screens.
- `.cursor/rules/*.mdc` is a legacy Cursor compatibility layer. Do not treat it as the primary source when it conflicts with `AGENTS.md`, `README.md`, `DESIGN.md`, or current runtime reality.
- Working logs/templates are in `.cursor/docs/*.md`.
- If README and rule files conflict, follow README + current runtime reality.

## 7. Current Rule Set
- `.cursor/rules/beautybot.mdc`
- `.cursor/rules/code_implementation_workflow.mdc`
- `.cursor/rules/verification_workflow.mdc`
- `.cursor/rules/dba_workflow.mdc`
- `.cursor/rules/frontend-design.mdc`

## 8. Legacy Cleanup Note
Older SQLite/systemd-first instructions were superseded by Docker/Postgres workflow.
Legacy details remain in git history and must not be used as default runbook.

## 8.1 Current Platform State
- LocalOS is now an operating layer for local businesses, not only a map-card SEO analyzer.
- Current user-facing work areas include:
  - map/card audit, parser queue, external account snapshots, public audit/sales-room pages;
  - services management, SEO suggestions, service menu compression/grouping, internal apply/rollback and soft archive through `userservices.is_active`;
  - external reviews, unanswered-review queues, reply drafts, bulk reply draft generation and manual publication helpers;
  - news drafts, social post drafts, content plans, content history and public articles/cases/documents;
  - finance dashboard, KPI history, import previews, finance apply approvals and average-ticket work;
  - partnerships and supervised outreach through `prospectingleads`: search/import, shortlist, channel selection, draft offers, approval, capped batches, delivery status and reactions;
  - Operator as the governed work center across `/dashboard/operator` and Telegram owner-bot commands;
  - agent product cockpit with compiled workflows, preview/preflight, provider routes, approvals, run journal and observability.
- OpenClaw / Action Orchestrator remains the execution boundary for policy, approval, billing, audit, callbacks, retry/DLQ/outbox and recovery.
- Canonical agent docs:
  - product model: `PRODUCT.md`;
  - agent map: `docs/AGENT_REGISTRY_V1.md`;
  - compiled agent architecture: `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`;
  - AI-agent overview: `docs/agents/index.md`;
  - tool/capability boundaries: `docs/agents/tool-registry.md` and `docs/agents/capabilities.md`;
  - partnership backlog: `docs/PARTNERSHIP_ROADMAP_BACKLOG.md`.
- Do not introduce a second lead table for current supervised outreach unless the user explicitly asks for the full outreach schema migration; the transitional flow uses `prospectingleads`.
- Do not claim autonomous provider writes. Review replies, news/social posts, outreach sends, payments, destructive changes, access changes and bulk mutations require the documented approval/manual-publication boundary.

## 9. Terminal Sessions (tmux)
- Use `tmux` for all long-running operations on server and local machine.
- Run builds, dependency installs, log tailing, and deployment commands inside a named `tmux` session.
- Default flow:
  1) `tmux new -s deploy`
  2) run long commands inside the session
  3) detach with `Ctrl+b` then `d`
  4) reattach with `tmux attach -t deploy`
- Do not run long operations in a plain SSH shell if connection drops are possible.

## 10. Code Standards
- Never typecast.
- Never use `as`.

## 11. Autonomous Development Trigger
- Trigger phrase: `Автономная разработка`.
- When this phrase appears in a user request, the agent must switch to autonomous execution mode for the current task.
- Autonomous mode is proof-loop based by default (mandatory).
- In autonomous mode, the agent must use the canonical brief from `agents/autonomous_development_brief.md`.
- Proof-loop entrypoint:
  - `scripts/proof_loop.sh init <TASK_ID> "<TASK_TEXT>"`
- If task bundle already exists, do not re-init; continue same `<TASK_ID>`.
- Task-specific profiles are optional and are loaded only when relevant to the task domain:
  - parser/network reliability: `agents/profiles/parsing_network_stability.md`
- If the user provides task-specific constraints, treat them as higher priority than defaults in the brief.
- Execution policy in autonomous mode:
  1) implement a minimal fix hypothesis
  2) run relevant checks
  3) evaluate against DoD
  4) iterate until success criteria are met or a hard blocker is found
- Hard blocker policy: stop only for destructive/irreversible actions, risky DB schema/data operations, or missing required access.

## 11.1 Autonomous Control Phrases
- `Статус автономной разработки`
  - Run: `scripts/proof_loop.sh status <TASK_ID>`
  - Return concise status of current proof bundle and next step.
- `Проверка автономной разработки`
  - Run: `scripts/proof_loop.sh validate <TASK_ID>`
  - Return `valid/invalid` and exact missing files/errors when invalid.

## 11.2 Goal-Oriented Autonomous Development
- For broad implementation goals, keep the original user objective intact and decompose it into measurable phases.
- Use `agents/autonomous_development_brief.md` as canonical execution behavior.
- Apply the Supergoal-inspired rules there for recon, adaptive phases, preflight, recovery, final audit, and learning writeback.
- Do not introduce a second competing workflow state outside `.agent/tasks/<TASK_ID>/` unless explicitly requested.

## 12. Curated Subagent Profiles
- Curated third-party profiles are stored in `agents/subagents/`.
- Source snapshot used: `Kastrulkin/awesome-codex-subagents`.
- Current curated groups:
  - `agents/subagents/core-dev/` (frontend/fullstack/ui/qa/refactoring)
  - `agents/subagents/data-ai/` (postgres/prompt/seo/payments)
  - `agents/subagents/business/` (product/project/sales/ux)
  - `agents/subagents/meta/` (installer/coordinator/performance/workflow)
- Usage guidance is documented in `agents/subagents/README.md`.
- If adding new upstream profiles, prefer curation over bulk import and document rationale in the README.

## 13. Product Documentation Rules
- Product name for external-facing docs: LocalOS.
- Short description: LocalOS is an operating layer for local businesses that helps manage map presence, services, reviews, content, finance, locations, partnerships, and supervised automation.
- Primary audiences:
  - local business owners and managers;
  - specialists managing local SEO/map listings for clients;
  - networks with several locations;
  - internal or external AI agents that need safe access to LocalOS workflows.
- Documentation style:
  - concise, factual, and implementation-aware;
  - separate discovery docs from API/agent integration docs;
  - mark capability status as `available`, `beta`, `internal`, `planned`, or `gap`;
  - include inputs, outputs, limits, approval requirements, and examples when an API really exists.
- Do not invent:
  - MCP availability;
  - public OpenAPI completeness;
  - provider write support;
  - prices, countries, guarantees, or legal claims;
  - fully autonomous publish/send/payment behavior.
- Human approval is mandatory in docs for publish, payments, destructive actions, mass changes, external sends, and actions made on behalf of a business in third-party systems.
- Done means:
  - docs link to the relevant source-of-truth files;
  - real capabilities are distinguished from gaps;
  - examples do not imply unsupported behavior;
  - AGENTS.md remains a development rulebook and is not replaced by product marketing copy.
