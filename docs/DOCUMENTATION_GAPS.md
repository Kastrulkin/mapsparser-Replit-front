# Documentation and Integration Gaps

These gaps prevent LocalOS from being fully self-discoverable by external AI agents.

## Public API Contract

Status: `gap`

There is no complete OpenAPI spec for the production API. Existing route lists are useful but not enough for reliable third-party integration.

Recommended next step:

- generate an OpenAPI draft from the currently supported endpoint allowlist;
- add schema examples for request/response;
- add contract tests.

## MCP Server

Status: `gap`

No confirmed MCP server exists in the repository. A lightweight `/localos-agent-tools.json` capability map exists, but it is not an MCP server and should not be treated as executable tooling by itself.

Recommended next step:

- define a narrow MCP surface for read-only card audit, finance dashboard, service suggestions, review drafts, and content drafts;
- keep write/publish/send actions behind approval tools.

## Agent Tokens

Status: `gap`

Current APIs use user bearer sessions. External agents need scoped, revocable, tenant-bound tokens.

Recommended next step:

- add `agent_api_tokens` or equivalent;
- scopes by capability;
- rate limits;
- audit trail;
- token revocation UI.

## Capability Registry Endpoint

Status: `available`

`GET /api/agents/capabilities?business_id=...` returns the business-scoped
capability registry for the authenticated user. The response includes capability
risk, approval requirement, provider candidates, connector requirements, current
configured provider status, and safety rules. Secrets are not returned.

Recommended next step:

- add this endpoint to the generated OpenAPI contract;
- expose it in external-agent docs after agent-token scopes are implemented.

## Unified Approval API

Status: `partial/gap`

Several flows have approvals, but there is no single approval envelope for all agent actions.

Recommended next step:

- common approval object;
- pending/approved/rejected/expired states;
- actor, approver, idempotency key, trace id;
- result ledger.

## External Publishing Contract

Status: `partial/gap`

Google Business publish endpoints exist. Yandex/2GIS write contracts are not documented as stable public publish APIs.

Recommended next step:

- provider capability matrix;
- per-provider write limitations;
- publish preview and post-publish verification.

## Pricing and Billing Documentation

Status: `gap`

This documentation does not define public pricing. Existing billing/payment code should be documented separately after product decisions are current.

Recommended next step:

- tariff catalog;
- feature entitlements;
- API usage limits;
- billing events for agent runs.

## Multi-Country Readiness

Status: `partial/gap`

The frontend and public pages have multilingual elements, but country-specific provider, legal, billing, and data-retention rules need explicit docs.

Recommended next step:

- country/provider matrix;
- language support matrix;
- data residency/legal notes.
