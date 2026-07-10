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
| User-created Agents | `beta` | one-off/manual read, draft and safe internal-draft runs through AgentBlueprint | async runs and scheduler are cohort-flagged; external actions remain behind approval |
| Public MCP server | `gap` | do not claim MCP availability | only documented static manifests/OpenAPI aliases are available |

## LocalOS Operator

[LocalOS Operator](localos-operator.md) is the beta control layer above the dashboard. It treats web chat, action cards and Telegram owner-bot commands as surfaces for the same governed core.

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
- [Harness architecture](harness-architecture.md)
- [Tool registry](tool-registry.md)
- [Planning and goal loops](planning-and-goals.md)
- [Agent use cases](use-cases.md)
- [Popular account examples](popular-account-examples.md)
- [Approval policy](approval-policy.md)
- [Agent API security model](security-model.md)
- [API endpoints](../api/endpoints.md)
- [API examples](../api/examples.md)
