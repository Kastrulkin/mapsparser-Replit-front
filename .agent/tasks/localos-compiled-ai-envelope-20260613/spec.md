# Task Spec: localos-compiled-ai-envelope-20260613

## Metadata
- Task ID: localos-compiled-ai-envelope-20260613
- Created: 2026-06-13T09:15:04+00:00
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- agents/autonomous_development_brief.md
- docs/LOCALOS_COMPILED_AI_ENVELOPE_OVER_OPENCLAW_V1.md
- docs/LOCALOS_AGENT_ARCHITECTURE_V1.md

## Original task statement
Сделать LocalOS product/policy envelope поверх OpenClaw: пользователь описывает агента обычным языком, система уточняет детали, понимает нужные сервисы, компилирует workflow в проверяемый executable plan, показывает подключения/стоимость/риски, требует approval и запускает safe preview перед активацией в рамках лимитов подписки.

## Current phase scope
Phase 5 of the remaining implementation: Maton delivery draft/send route handler.

Selected Maton provider-route contracts must become a real LocalOS runtime handler behind the compiled workflow contract:
- safe preview creates only a delivery draft/request artifact;
- approved production run may dispatch through the existing channel router and Maton bridge;
- no Maton send happens from prompt text, preview mode, or missing approval;
- the run stores an auditable delivery artifact.

## Acceptance criteria
- AC1: Runner recognizes `maton_external_account_bridge` contracts from blueprint metadata for `communications.send*` capabilities.
- AC2: Safe preview Maton delivery creates a `maton_delivery_request` artifact and does not call `dispatch_with_routing`.
- AC3: Production Maton dispatch requires prior approved approval and explicit `dispatch_mode=send_after_approval` plus `external_side_effects_allowed=true`.
- AC4: Approved dispatch uses the existing `load_business_channel_context` + `dispatch_with_routing` route with `preferred_provider=maton` and `force_channel_id=maton_bridge`.
- AC5: Maton delivery artifacts record provider, handler, binding, external account, delivery state, router result, policy envelope, and whether external dispatch was performed.
- AC6: Agent-related tests and frontend production build pass.

## Constraints
- Do not introduce a second Maton integration path.
- Do not allow autonomous sends without LocalOS approval gate.
- Do not change production schema in this phase.
- Do not create a new communication-agent entity; communication remains a blueprint category/capability.

## Non-goals
- Full customer-recipient routing UX.
- Bulk Maton campaigns.
- Google Sheets read or LocalOS finance write; those remain next phases.
- Production schema migration.

## Verification plan
- Focused Maton/OpenClaw runner tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -k 'maton_delivery or openclaw_preview_observations or creates_drafts_after_shortlist' -x`
- Unit/integration tests: `PYTHONPATH=src python3 -m pytest -q tests/test_agent_blueprint_layer.py -x`
- Frontend build: `npm --prefix frontend run build`
