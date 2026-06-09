# Task Spec: communication-agents-showcase-20260609

## Metadata
- Task ID: communication-agents-showcase-20260609
- Created: 2026-06-09T11:40:35+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре
- Working directory at init: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md

## Original task statement
Stage 5 communication agent showcase: five MVP communication blueprints with trigger, audience, consent, persona/template, approval, send capability, and delivery/outcome journal; draft-only or approved-batch-only, no autonomous sends.

## Acceptance criteria
- AC1: Communication agent showcase exposes five MVP blueprint templates: appointment reminder, post-visit follow-up, inactive-client winback, package offer after relevant service, and inbound request reply draft.
- AC2: Each MVP blueprint has trigger, audience rules, consent rules, message template/persona, approval policy, send/draft capability, and delivery/outcome journal metadata.
- AC3: Safety contract forbids autonomous sends: every template is either `draft_only` or `approved_batch_only`, records `external_dispatch_performed=false`, and requires human approval before external delivery.
- AC4: Existing architecture is reused: communication agents remain `AgentBlueprint.category = communications`; no new communication-agent entity/table/runtime is introduced.
- AC5: Product entry point surfaces communications as a normal Agent Studio scenario.

## Constraints
- Reuse AgentBlueprint, Agent Compiler, AgentBlueprintRunner and ActionOrchestrator/OpenClaw capability map.
- Do not introduce production schema changes.
- Do not modify production data.
- Do not add a standalone communication-agent runtime.

## Non-goals
- No full autonomous dispatch.
- No external provider send integration beyond existing capability request boundary.
- No new database table for agents or communication agents.

## Verification plan
- Build: `cd frontend && npm run build`
- Unit tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py`
- Integration tests: compiler/template selection covered in agent layer tests; no DB migration/server deploy in this stage.
- Lint: `rg -n "\bas\b" ...` on changed files to avoid new typecasts.
- Manual checks: review diff for no new entity/table/runtime and doc consistency.
