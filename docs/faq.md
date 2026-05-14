# FAQ

## Is LocalOS only for beauty salons?

No. Beauty has the most detailed service guardrails in the current optimizer, but LocalOS is structured for local businesses across industries. Industry-specific rules must not be applied globally.

## Can an AI agent publish content automatically?

Not by default. Drafting is allowed where endpoints support it. Publishing, sending, payment, destructive, and external-system actions require human approval unless a narrower business policy explicitly allows the action.

## Is there a public MCP server?

Not confirmed in the current repository. Treat MCP as a gap until a server, tool manifest, auth rules, and tests are added.

## Is the API stable?

Some endpoints are mature enough for internal UI use. This documentation marks them by status. External integrations should start with a small allowlist of endpoints, not the entire Flask app.

## Can LocalOS work with several countries?

The product direction supports multiple languages and multiple countries, and public audit pages include multilingual UI. Country-specific provider rules, billing, legal text, and data handling still need explicit validation.

## Does LocalOS replace CRM?

No. LocalOS can ingest or summarize operational data and provides CRM adapter scaffolding for finance, but it is not a full CRM replacement.

## Where should agents start?

Start with [Agent Capabilities](agents/capabilities.md), [Approval Policy](agents/approval-policy.md), and [API Examples](api/examples.md).
