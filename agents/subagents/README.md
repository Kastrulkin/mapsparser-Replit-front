# Curated Subagents (from awesome-codex-subagents)

Source repository:
- https://github.com/Kastrulkin/awesome-codex-subagents

This folder contains a curated set of profiles that are useful for LocalOS day-to-day delivery.

## What was added

### Core implementation
- `core-dev/frontend-developer.toml`
- `core-dev/fullstack-developer.toml`
- `core-dev/ui-fixer.toml`
- `core-dev/qa-expert.toml`
- `core-dev/refactoring-specialist.toml`

### Data / DB / domain
- `data-ai/postgres-pro.toml`
- `data-ai/prompt-engineer.toml`
- `data-ai/seo-specialist.toml`
- `data-ai/payment-integration.toml`

### Product / operations
- `business/product-manager.toml`
- `business/project-manager.toml`
- `business/sales-engineer.toml`
- `business/ux-researcher.toml`

### Orchestration
- `meta/agent-installer.toml`
- `meta/multi-agent-coordinator.toml`
- `meta/performance-monitor.toml`
- `meta/workflow-orchestrator.toml`
- `meta/pied-piper-localos.toml` (local custom profile)

## Recommended use in LocalOS

- Frontend regressions/UX polish: `frontend-developer`, `ui-fixer`
- Full path feature (API + UI): `fullstack-developer`
- DB and migrations: `postgres-pro`
- Prompt/pipeline tuning: `prompt-engineer`
- SEO quality controls: `seo-specialist`
- Billing/payments changes: `payment-integration`
- Sprint scoping and prioritization: `product-manager`, `project-manager`
- Outreach demo scripts and fit/gap messaging: `sales-engineer`
- Multi-thread orchestration: `multi-agent-coordinator`, `workflow-orchestrator`
- Runtime signal triage: `performance-monitor`

## Note about pied-piper

`pied-piper` is **not present** in the current upstream repository snapshot I pulled.
Added local equivalent: `meta/pied-piper-localos.toml` with LocalOS-specific orchestration loops.
