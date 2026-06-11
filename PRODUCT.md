# LocalOS Product Operating Model

## Purpose

LocalOS is an operating layer for local businesses. It helps owners, managers, agencies, networks, and supervised AI agents manage map presence, services, reviews, content, finance, locations, partnerships, and safe automation.

This document is the product source of truth for UI and implementation decisions. `README.md` remains the technical runbook. `docs/DASHBOARD_DESIGN_BRANDBOOK.md` remains the visual dashboard brandbook. This file answers: who the product serves, what user work matters, and what LocalOS must never imply.

## Primary Users

- Local business owners and managers who need a clear next step, not technical configuration.
- Specialists managing local SEO and map listings for clients.
- Networks with several locations and repeated operational workflows.
- Internal and external AI agents that need bounded, auditable access to LocalOS workflows.

## Product Promise

LocalOS turns fragmented local-business operations into supervised workflows:

- understand the business state;
- propose useful next actions;
- prepare drafts, checks, exports, and requests;
- ask for human approval before risky actions;
- record what happened in a traceable journal.

LocalOS is not a fully autonomous publishing, payment, or messaging system. It can automate preparation and controlled execution, but user-facing docs and UI must not imply unsupported autonomous sends, destructive changes, third-party writes, or payments without approval.

## AI Agents Canon

An agent is a product object, not a technical workflow editor.

- `Agent` is the user-facing product object.
- `Persona` is voice and style, backed by legacy `AIAgents` where needed.
- `Blueprint` is the workflow logic.
- `Compiled Workflow` is the validated executable plan.
- `Capability` is a permitted action.
- `Provider` is the physical connector/executor behind a capability: native LocalOS, Maton.ai, OpenClaw, Composio, or manual handoff.
- `Run` is one execution.
- `Approval` is a human gate.
- `OpenClaw` / `ActionOrchestrator` is the execution boundary.

Communication is a blueprint category, not a separate product entity called "communication agent".

Agents must never bind directly to a provider in user-facing logic. User intent
compiles to capabilities, and LocalOS resolves the provider behind approval,
limits, billing, and audit. Existing LocalOS integrations and Maton.ai are
available provider sources now; Composio is a future provider source for broader
OAuth/tool coverage.

Reference custom-agent path: "read new payments from Google Sheets and create
LocalOS finance transactions" compiles to `google_sheets.read_rows` plus
`finance.transaction.create`. The first capability resolves connector/provider
access; the second prepares normalized LocalOS Finance proposals. Actual finance
writes stay behind approval, limits, duplicate checks and audit.

AI may help create or edit an agent, but the product promise is a compiled
workflow, not a runtime that improvises on every run. GigaChat can extract
design-time intent and propose sources, destinations, capabilities and required
connectors. LocalOS must then validate and save deterministic blueprint steps.
Runtime executes the compiled workflow; runtime LLM calls are allowed only as
explicit priced/audited steps when the workflow truly needs generation or
classification.

Compiled workflows pass data through explicit step mappings, not hidden prompt
memory. For example, a Google Sheets read step can expose
`orchestrator.result.rows`, and the finance request step maps that value into
its `rows` payload before policy/orchestrator execution. The saved blueprint is
the runtime source of truth.

Runs should fail early with a connection preflight when an external source is
missing. Native LocalOS destinations, such as Finance, are already available
inside the product boundary and should not be presented as another business
profile to connect.

Scheduled agents use the same compiled runtime. A `schedule.daily` trigger
records a scheduler event, runs connection preflight, then starts the saved
blueprint version through the normal runner. It is not a separate cron script
that bypasses approvals, audit, limits, billing or recovery. Worker dispatch is
an explicit opt-in (`AGENT_SCHEDULE_DISPATCH_ENABLED`), so deploying code does
not silently start customer agents.

## Mandatory Human Approval

Human approval is mandatory for:

- external sends and mass communication;
- publication to third-party systems;
- payments and billing settlement;
- destructive changes;
- actions performed on behalf of a business in third-party systems;
- any capability whose policy says approval is required.

The UI must explain approval in user language: what is waiting, why it is waiting, and what happens after approve/reject.

## Product Screen Model

Every product screen must have one dominant job.

- `Cockpit`: understand state and choose next action.
- `Create`: describe intent, review preview, create safely.
- `Manage`: edit logic, data, connections, runs, learning, and approvals.
- `Advanced`: inspect raw runtime details, ledgers, traces, and provider boundaries.

Technical internals can exist, but they must not be the first layer of the product UI.

## UI Process

Use this process for LocalOS product UI work:

1. `audit`: identify clutter, unclear labels, competing actions, and exposed internals.
2. `distill`: remove, collapse, or relocate anything outside the screen's dominant job.
3. `shape`: define the information architecture and states before styling.
4. `implement`: reuse LocalOS primitives and existing data contracts.
5. `harden`: verify responsive behavior, empty states, errors, overflow, and permissions.
6. `polish`: tighten copy, spacing, visual hierarchy, and final screenshots.

This process is adapted from the `taste-skill` / `impeccable` design workflow, but LocalOS product screens are operational dashboards, not marketing pages.

## Agent Product Requirements

The agents area must make these answers obvious:

- What agents exist?
- Which ones are active, paused, drafts, waiting for approval, or errored?
- What does the selected agent do?
- What does it need next?
- What ran last?
- What needs approval?
- What data and connections are required?
- What did learning/versioning change?
- Where can a superadmin inspect raw technical details?

The first screen should not look like a workflow/debugger.
