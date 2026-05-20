# LocalOS for AI Agents

LocalOS can be used as a supervised operating layer for AI agents working with local businesses.

The safe pattern is:

1. Read business context.
2. Prepare a draft, audit, recommendation, or preview.
3. Ask for approval when the action affects customers, money, public content, external accounts, or irreversible data.
4. Execute only the approved action.
5. Record outcome and expose it to the business.

## What Agents Can Do Today

- Read and summarize map/card data through existing audit and business APIs.
- Generate service optimization suggestions.
- Draft review replies.
- Draft news/posts and content plans.
- Read finance dashboard, data quality, recommendations, history, import previews, and CRM sync previews.
- Work with partnership leads, matching, drafts, approvals, batches, delivery status, and reactions.
- Route Telegram/WhatsApp messages through configured AI-agent webhooks.
- Help superadmin review industry-pattern proposals.

## LocalOS Operator

[LocalOS Operator](localos-operator.md) is the beta main control layer above the dashboard. It treats web chat and Telegram as two surfaces for the same governed Operator core.

Sprint 1 includes the first cached-data web intent at `/dashboard/operator`: `Что требует моего внимания сегодня?`. Sprint 2 connects the same cached brief to the existing Telegram owner-bot `client_today` flow. Sprint 3 adds proposal-only `paid_action_offers` for paid refresh/generation consent. Sprint 4 persists business-level consent policies and limit settings for those offers. Sprint 5 adds read-only paid action preflight for map refresh. These sprints do not run paid refreshes, AI generation, external provider writes, credit charges, or publication.

The Operator model keeps one context, one permission system, one credit/usage ledger, one approval policy, and one audit trail across web and Telegram. Sprint 0 defines the product contract only; it does not imply that the web-chat runtime or Telegram Operator runtime is fully implemented.

## What Agents Must Not Assume

- No public MCP server is confirmed.
- Not every Flask endpoint is a stable public API.
- Not all external providers support write actions.
- Publishing and sending require human approval.
- Review reply publishing to maps is not currently autonomous; LocalOS can prepare drafts, while users copy and publish manually unless a provider write flow is explicitly implemented and approved.
- Billing and payment operations must not be automated by a general agent.

## Related Docs

- Machine-readable tool map: `/localos-agent-tools.json`
- Minimal Agent API OpenAPI contract: `/localos-agent-openapi.json`
- Sandbox self-test: `POST /api/agent-api/self-test`
- [Capabilities](capabilities.md)
- [LocalOS Operator](localos-operator.md)
- [Harness architecture](harness-architecture.md)
- [Tool registry](tool-registry.md)
- [Planning and goal loops](planning-and-goals.md)
- [Agent use cases](use-cases.md)
- [Approval policy](approval-policy.md)
- [Agent API security model](security-model.md)
- [API endpoints](../api/endpoints.md)
- [API examples](../api/examples.md)
