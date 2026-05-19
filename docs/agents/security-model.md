# Agent API Security Model

Status: `beta/internal`

This page defines the security model for Agent API and future MCP access. The first technical foundation exists in code, but it is not a complete public Agent API product yet.

## Principle

LocalOS does not try to guess whether an agent is good or bad. It limits possible damage through identity, scopes, sandbox mode, approval, rate limits, abuse detection, and audit trails.

## Agent Client Registry

Future public agent access should register every integration as an `agent_client`.

Required fields:

- `client_id`;
- `owner_user_id`;
- `organization_name`;
- `contact_email`;
- `status`: `sandbox`, `live`, `suspended`;
- `allowed_scopes`;
- `rate_limits`;
- `created_at`;
- `last_seen_at`.

New clients start in `sandbox`. Current endpoint: `POST /api/agent-api/clients` with superadmin session auth.

## Scopes

Recommended first scopes:

- `audit:read`;
- `services:draft`;
- `reviews:draft`;
- `content:draft`;
- `finance:read`;
- `partners:read`;
- `approvals:create`;
- `publish:request`.

Do not grant direct `publish`, `delete`, `payment`, or broad admin scopes by default.

## Sandbox First

New integrations must start with:

- demo business data;
- fake financial data;
- no customer messages;
- no real external publishing;
- no access to live credentials;
- no destructive actions.

Live access requires manual review and scope approval.

## Approval Boundary

Agents may prepare drafts, previews, summaries, recommendations, and risk notes.

Agents must not directly:

- publish posts or review replies;
- mass edit card data;
- send messages to customers, partners, or prospects;
- initiate payments or billing changes;
- delete, disable, rollback, or bulk update records;
- act in external systems on behalf of a business.

For these actions, agents must create an approval request. Current endpoint: `POST /api/agent-api/approvals/request` with `X-LocalOS-Agent-Key`.

## Risk Levels

Every agent action should be classified:

- `low`: read an audit, list services, summarize data;
- `medium`: generate a draft, prepare recommendations, preview import;
- `high`: bulk update proposal, CRM sync, financial import after preview;
- `critical`: publish, payment, deletion, credential change, external-system action.

Higher risk requires stronger approval, tighter limits, and better logging.

## Agent Action Ledger

Every agent call should be logged to `agent_action_ledger` or an equivalent audit trail.

Recommended fields:

- `agent_client_id`;
- `business_id`;
- `action_type`;
- `risk_level`;
- `input_summary`;
- `output_summary`;
- `approval_id`;
- `status`;
- `ip`;
- `user_agent`;
- `created_at`.

Never log raw secrets, passwords, access tokens, or full payment credentials.

## Abuse Detection

Flag behavior such as:

- `business_id` enumeration;
- access attempts to businesses outside the tenant;
- repeated auth failures;
- requests without required scope;
- high-volume export attempts;
- attempts to bypass approval;
- anomalous request volume;
- mismatch between declared use case and actual calls.

Response options:

- rate limit;
- cooldown;
- remove dangerous scopes;
- require re-authentication;
- move client to manual review;
- suspend client;
- notify superadmin in Telegram.

## Rate Limits

Rate limits should apply by:

- `agent_client_id`;
- IP;
- business;
- scope;
- risk level;
- endpoint family.

Read, draft, approval, export, and external-action requests should have separate limits.

## Webhook Security

Webhook callbacks should use:

- signed payloads;
- timestamp;
- replay protection;
- idempotency key;
- secret rotation;
- explicit retry policy.

## Superadmin Alerts

High-risk or suspicious activity should notify superadmin with:

- client;
- business;
- action;
- risk level;
- reason code;
- proposed restriction;
- actions: allow, restrict, suspend, require review.

## Done Criteria

Agent API is safe enough to open only when a malicious or compromised integration cannot:

- read another tenant's data;
- publish without approval;
- send customer messages without approval;
- change billing or payments without approval;
- perform destructive actions without approval;
- avoid audit trails.

## Current Implementation

Implemented foundation:

- `agent_clients` table;
- `agent_action_ledger` table;
- `agent_discovery_events` table for docs/API discovery tracking;
- scoped agent key authentication;
- sandbox-first client creation;
- superadmin UI for agent clients, scopes, status, key rotation, ledger and discovery events;
- direct blocking for dangerous actions;
- pending human approval request endpoint;
- superadmin ledger view;
- 24-hour agent activity summary in the superadmin morning Telegram digest;
- machine-readable `/localos-agent-policy.json`.
- Telegram bot-to-bot security foundation: sender classification and routing plan in [Telegram Bot-to-Bot Security](telegram-bot-to-bot-security.md).

Still planned:

- full rate-limit middleware;
- live client promotion workflow;
- Telegram alert wiring for abuse signals;
- webhook replay protection middleware;
- public MCP tool server.
