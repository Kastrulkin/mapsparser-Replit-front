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

## What LocalOS Does Today

LocalOS is useful when a business owner asks practical operating questions:

- Why are map listings not bringing enough calls, routes, bookings, or trust?
- Which services, descriptions, prices, categories, photos, reviews, and posts need attention?
- What should be prepared now: reply draft, service rewrite, news draft, partner shortlist, finance import, or map refresh?
- What changed after the business acted, and what still needs manual review?

Current product surfaces cover:

- map/card audit, parsing, public audit offers, profile quality and freshness signals;
- services list management, SEO suggestions, service menu compression/grouping, internal apply and rollback;
- review storage, unanswered-review workflows, reply drafts, bulk draft generation and manual publication helpers;
- news drafts, social post drafts, content history, content plans and public content materials;
- finance dashboard, data quality, imports, KPI history, average-ticket work and approved finance apply flows;
- partnerships and supervised outreach: search/import, card parsing, contact enrichment, match reasons, public signals, founder-led personalization, versioned multichannel drafts, approvals, stop-on-reply, delivery outcomes and strategy learning events;
- Operator as a work center across web and Telegram for attention briefs, review/content/service/partnership actions, map refresh jobs and billing visibility;
- AI agents as compiled workflows with preview, preflight, provider resolution, approvals, run journal and audit.

## Beauty Salon Operating Scenarios

Beauty salons are a primary use case and should be described through business outcomes, not internal modules.

- Low season: LocalOS can inspect card health, service structure, reviews, news cadence and partner opportunities, then prepare a short action queue for the month.
- Service menu clarity: LocalOS can find duplicates and overloaded service lists, propose groups, let the user edit final categories/names/descriptions, and apply only confirmed internal changes.
- Average ticket: LocalOS can help package services, show price ranges, expose add-on opportunities and connect service structure with finance/KPI review.
- Reputation: LocalOS can show unanswered or fresh reviews, prepare reply drafts, and keep external publication manual unless a supported provider write flow is approved.
- Partnerships: LocalOS can find nearby complementary businesses, prepare fit reasons and draft partner messages, but sending stays behind approval/capped dispatch.

## Outreach Sender Identity

Every campaign has one explicit sender mode that is included in the approved version and audit trail:

- `localos`: LocalOS prospects are contacted by LocalOS through a platform-scoped account;
- `partner_business`: a business contacts its own prospective partners through its tenant-scoped account;
- `localos_for_partner`: a superadmin may contact a prospective partner through a platform-scoped LocalOS account while transparently naming the represented business.

`localos_for_partner` is representation, not impersonation. The campaign remains scoped to the represented business, uses that business's confirmed services, audience, compatibility evidence and allowed offer, but uses the confirmed LocalOS identity and account. Every message must disclose both facts. LocalOS must never silently fall back between sender modes or select a global account merely because it was connected last. A sender-mode change creates a new preview/version and requires a new approval.

## Outreach Operating Model

LocalOS treats outreach as one supervised lifecycle, not as a text generator:

1. search or import a company into the shared `prospectingleads` source of truth;
2. attach a `localos_sales` or `client_partnership` workstream;
3. parse the public card, audit/match where applicable, enrich contacts from map payloads and the official website, and keep provenance;
4. classify Telegram entities so personal users remain recipients while channels/groups become radar evidence sources;
5. build an evidence ledger from map/audit facts, public websites, reviews, social activity, Telegram posts and partnership compatibility;
6. add the confirmed sender profile only after recipient evidence exists, producing the explicit chain observation → relevance bridge → founder story/proof → one CTA;
7. create and quality-check a versioned multichannel draft;
8. require human approval before queue/dispatch and repeat safety preflight before every touch;
9. stop all future channels on any human reply and record the attributable outcome for the learning loop.

The recommended default sequence is Telegram day 0 for the signal, email day 3 for founder story, the next available channel day 7 for proof/useful material, and a respectful close on day 12. Telegram and email are the current automatic channel boundary when their direct-send and reply-sync capabilities are connected and permitted. WhatsApp, MAX, VK, SMS and other channels remain manual until a verified adapter supports both delivery and reply sync.

An outreach fact must have evidence ID, source URL, date/freshness and confidence. Hypotheses remain explicitly labeled. A missing material fact returns `needs_evidence`; it must not be replaced with a generic template. Sender claims are accepted only from confirmed `approved` or `observed` profile facts.

Learning events store strategy dimensions and outcomes such as sent, reply, question, hard no, unsubscribe, meeting, conversion and no reply. They support evidence-based strategy comparison; LocalOS does not claim automatic online fine-tuning of the production language model.

Canonical implementation/status reference: [`docs/OUTREACH_SYSTEM.md`](docs/OUTREACH_SYSTEM.md).

## Product Boundaries

LocalOS may prepare drafts, previews, recommendations, imports, refresh requests, grouped service drafts and internal changes after explicit confirmation. It must not imply that it automatically publishes to maps/social networks, sends outreach/customer messages, pays, deletes, bulk-mutates, or changes third-party systems unless the exact provider write flow is implemented, tested, documented and approved by the user.

Internal LocalOS mutations can still require approval when they hide, archive, overwrite, apply suggestions, import finance data, change access, or affect a business workflow. External publication and communication are always separate from draft generation.

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

There are not two executable products called "simple Agents" and "Compiled
Agents". The simple builder is the user experience; every executable result is
an `AgentBlueprint` with a compiled workflow. The three explicit execution
modes are:

- `one_off`: no automatic launch; the same agent may still be run again with
  new parameters;
- `manual`: a reusable agent launched by the owner;
- `scheduled`: an explicitly activated agent with time and IANA timezone.

Legacy agents without a confirmed mode may be tested, but cannot perform work
or run automatically until the owner confirms the mode.

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

Runs fail early with a connection preflight when an external source is
missing. Native LocalOS destinations, such as Finance, are already available
inside the product boundary and should not be presented as another business
profile to connect. In the controlled beta, accepted runs are idempotently
queued and executed by the worker. The HTTP request is not the lifetime of the
task; a saved run can recover after an app or browser restart.

The candidate and active version are separate contracts. Preview always tests
the candidate. Reusable working runs use only the explicitly active version;
activation requires a successful preview, and rollback selects an earlier
tested version without launching it. Run forms come from the selected version's
`inputs_schema_json`, while server-side validation removes reserved service
fields and rejects unknown or invalid values.

Preview is free. A production run reserves up to two credits, settles one
credit per started 1,000 recorded tokens within that reservation, releases the
unused part, and records any beta overage without charging it. One
`idempotency_key` maps to one run and one reservation.

The primary result contract is `business_result` plus `result_state`. The UI
must bind approvals and artifacts to that exact run; an older pending approval
must never replace the completed result of a newer run.

Scheduled agents use the same compiled runtime. A `schedule.daily` trigger
records a scheduler event, runs connection preflight, then starts the saved
blueprint version through the normal runner. It is not a separate cron script
that bypasses approvals, audit, limits, billing or recovery. Worker dispatch is
an explicit opt-in (`AGENT_SCHEDULE_DISPATCH_ENABLED`), so deploying code does
not silently start customer agents.

The first Agents beta permits one-off/manual read, draft and safe internal-draft
capabilities. Capability catalog entries declare `runtime_status` and
`beta_enabled`; request-only or planned capabilities may remain visible in
technical catalogs but cannot activate a compiled workflow in this cohort.

Current rollout boundary (verified 19 July 2026): async execution is enabled
only for three beta businesses. Scheduler dispatch code and its feature flag
are deployed, but production has no active confirmed scheduled blueprint and no
recorded scheduler event yet. Documentation must therefore describe scheduled
execution as implemented but not production-proven, not as generally launched.

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

## Operator Product Model

Operator is the goal-oriented work center above the dashboard. It should answer "what needs my attention and what can LocalOS prepare next?" rather than expose raw modules first.

Operator may surface:

- cached attention briefs and state cards;
- review reply drafts, news/social drafts and service suggestions;
- map refresh jobs, reliability states, retry requests and billing visibility;
- partnership work queues and draft offers;
- links into detailed dashboard sections for review and manual completion.

Operator is not a separate bot product and not a permission bypass. Web chat, dashboard cards and Telegram owner-bot commands must share the same context, consent, credit, approval, audit and manual-publication boundaries.

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
