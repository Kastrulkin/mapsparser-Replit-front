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

## What Agents Must Not Assume

- No public MCP server is confirmed.
- Not every Flask endpoint is a stable public API.
- Not all external providers support write actions.
- Publishing and sending require human approval.
- Billing and payment operations must not be automated by a general agent.

## Related Docs

- Machine-readable tool map: `/localos-agent-tools.json`
- Minimal Agent API OpenAPI contract: `/localos-agent-openapi.json`
- [Capabilities](capabilities.md)
- [Harness architecture](harness-architecture.md)
- [Tool registry](tool-registry.md)
- [Planning and goal loops](planning-and-goals.md)
- [Agent use cases](use-cases.md)
- [Approval policy](approval-policy.md)
- [Agent API security model](security-model.md)
- [API endpoints](../api/endpoints.md)
- [API examples](../api/examples.md)
