# LocalOS for AI Agents

LocalOS can be used as a supervised operating layer for AI agents working with local businesses.

The safe pattern is:

1. Read business context.
2. Prepare a draft, audit, recommendation, or preview.
3. Ask for approval when the action affects customers, money, public content, external accounts, or irreversible data.
4. Execute only the approved action.
5. Record outcome and expose it to the business.

## What Agents Can Do Today

- Read scoped LocalOS business context: profile, card snapshots, audits, services, reviews, news drafts, finance summaries, locations, partnership leads and approved run history.
- Prepare drafts and recommendations: service SEO suggestions, service menu grouping, review replies, news/social posts, content plans, finance import previews, partner match reasons and outreach drafts.
- Request or inspect controlled actions: service suggestion apply, service grouping apply/rollback, finance apply, map refresh jobs, partnership batch approvals and manual-publication status.
- Use Operator surfaces to answer "what needs attention today?" and route the user to review/content/service/partnership/finance actions.
- Work through configured Telegram/WhatsApp webhooks and owner-bot control surfaces when the business has the required settings and scopes.
- Create and run `one_off` or `manual` Agents through a compiled `AgentBlueprint`, with typed inputs, candidate preview, explicit activation, durable run history and normalized business results.
- Help superadmin review internal proposals such as industry-pattern recalibration, while respecting privileged/admin boundaries.

Every account should also have a visible starter pack of common draft examples.
See [Popular account examples](popular-account-examples.md) for the canonical
10 examples and seed/backfill rules.

## Capability Status Overview

Status values used in this documentation:

- `available`: implemented and usable inside the documented LocalOS boundary.
- `beta`: implemented but provider access, workflow coverage, or production approval may be limited.
- `internal`: intended for superadmin, maintenance, testing, or controlled runtime surfaces.
- `planned`: intended product direction, not safe to present as ready.
- `gap`: explicitly unavailable; agents must not claim it works.

Current capability areas:

| Area | Status | Agent-safe use | Boundary |
| --- | --- | --- | --- |
| Card audit and map snapshots | `available/beta` | read existing data, request supported refreshes, summarize gaps | provider coverage varies; paid refresh uses consent/credits |
| Services optimization | `available` | prepare SEO suggestions and apply confirmed internal changes | no external card write unless separately implemented and approved |
| Service menu compression | `available` | propose groups, let user edit, apply confirmed LocalOS grouping/rollback | soft archive originals; no automatic external provider writes |
| Reviews | `available/beta` | read stored reviews, draft replies, bulk draft replies, mark manual publication | direct map publishing is provider-specific and must be documented before use |
| News and social drafts | `available` | prepare drafts and content history | publication remains manual unless a provider write flow is approved |
| Finance | `available/beta` | read KPIs, prepare import previews/proposals, apply only approved rows | money/billing/payment-related operations require approval |
| Partnerships and outreach | `beta` | search/import leads, classify fit, draft offers, prepare approval-ready batches | sending is capped, approved, and never implied by draft generation |
| Operator | `beta` | use attention briefs, action cards, refresh status, draft helpers and Telegram parity | same approval, billing and audit policy as dashboard workflows |
| User-created Agents | `beta` | one-off/manual read, draft and safe internal-draft runs through AgentBlueprint; typed parameters, version activation/rollback, queued execution and two independent read-only schedules are implemented | async runtime is limited to three beta businesses; both schedules completed day 1 of the required 7-day canary on 20 July 2026; external actions remain behind approval |
| Public MCP server | `gap` | do not claim MCP availability | only documented static manifests/OpenAPI aliases are available |

## Compiled Agents Runtime

There is one product called `Agents`. The natural-language builder is the
simple user surface; it compiles every executable agent into a versioned
`AgentBlueprint`. `AIAgents` supplies persona/voice for legacy chat scenarios
and is not a parallel workflow runtime.

Current runtime guarantees:

- explicit `one_off`, `manual` or `scheduled` execution mode;
- candidate version for preview and active version for reusable work;
- user parameters derived from `inputs_schema_json` and validated again by the
  backend;
- idempotent enqueue and one active queued/running/retry run per blueprint in
  the admitted async cohort;
- worker heartbeat, transient retry and browser-independent polling;
- free preview and a two-credit production reservation with actual settlement;
- `business_result` and approvals bound to the exact run;
- a computed execution contract that exposes the original request, candidate
  and active scenario, saved ordered steps, inputs, result and approval stops;
- server-derived run progress that survives page reload and never marks a step
  complete before the durable step journal does;
- external sends, publication, payments and destructive writes remain separate
  approved actions.

The product UI uses four user-facing sections: Overview, History, Scenario and
Settings. Overview owns the single next action and only previews the latest
result; the complete result belongs to a specific run in History. Scenario is
the readable projection of the compiled version, not an editable parallel
workflow.

The certified beta catalog currently allows read, draft and safe internal-draft
capabilities. Request-only writes can be represented and reviewed, but they do
not make a workflow eligible for autonomous activation. See
[Compiled AI Architecture v1](../LOCALOS_COMPILED_AI_ARCHITECTURE_V1.md) for
the exact runtime and rollout status.

Current production evidence and the gates that must not be declared complete
early are recorded in [Agents Beta Production Status](../AGENTS_BETA_PRODUCTION_STATUS.md).

## LocalOS Operator

[LocalOS Operator](localos-operator.md) is the beta control layer above the dashboard. It treats web chat, action cards and Telegram owner-bot commands as surfaces for the same governed core. The current domain-by-domain truth table is the [Operator capability coverage manifest](operator-capability-coverage.md).

Operator can currently expose:

- cached attention briefs: reviews without replies, pending approvals, content tasks, partnership leads, card/profile freshness and finance warnings;
- manual review intake, review reply draft generation, bulk draft generation and manual publication helpers;
- news/social draft generation and content history;
- services optimization suggestions and confirmed internal apply;
- read-only map refresh jobs, refresh result summaries, reliability states, retry requests and billing clarity;
- partnership queues and next-best-action links;
- Telegram parity for selected owner commands and completed refresh follow-ups.

The Operator model keeps one context, one permission system, one credit/usage ledger, one approval policy and one audit trail across web and Telegram. It does not publish replies, send customer messages, update third-party maps, bypass credits, or silently retry paid refreshes.

## What Agents Must Not Assume

- No public MCP server is confirmed.
- Not every Flask endpoint is a stable public API.
- Not all external providers support write actions.
- Publishing and sending require human approval.
- Review reply publishing to maps is not currently autonomous; LocalOS can prepare drafts, while users copy and publish manually unless a provider write flow is explicitly implemented and approved.
- Billing and payment operations must not be automated by a general agent.
- Draft generation does not imply apply/publish/send permission.
- Internal apply actions can still be risky when they hide, archive, overwrite, import, bill, or bulk-change LocalOS records.

## Related Docs

- Machine-readable tool map: `/localos-agent-tools.json`
- Minimal Agent API OpenAPI contract: `/api/agent-api/openapi.json`
- Static OpenAPI alias: `/localos-agent-openapi.json`
- Sandbox self-test: `POST /api/agent-api/self-test`
- [Capabilities](capabilities.md)
- [LocalOS Operator](localos-operator.md)
- [Operator capability coverage](operator-capability-coverage.md)
- [Harness architecture](harness-architecture.md)
- [Tool registry](tool-registry.md)
- [Planning and goal loops](planning-and-goals.md)
- [Agent use cases](use-cases.md)
- [Popular account examples](popular-account-examples.md)
- [Google Sheets reference agent](google-sheets-reference-agent.md)
- [Compiled AI architecture](../LOCALOS_COMPILED_AI_ARCHITECTURE_V1.md)
- [Approval policy](approval-policy.md)
- [Agent API security model](security-model.md)
- [API endpoints](../api/endpoints.md)
- [API examples](../api/examples.md)
