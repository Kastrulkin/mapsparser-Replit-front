# API Authentication

Most LocalOS API endpoints use a bearer session token.

## Login

Endpoint:

```http
POST /api/auth/login
Content-Type: application/json
```

Typical body:

```json
{
  "email": "owner@example.com",
  "password": "password"
}
```

Typical response includes an auth token used by the frontend as `auth_token`.

## Auth Header

Use:

```http
Authorization: Bearer <auth_token>
```

Common responses:

- `401` - missing, invalid, or expired token.
- `403` - authenticated but not allowed, or user/business is blocked.

## Business Access

Most business endpoints require `business_id`.

The backend checks:

- authenticated user;
- ownership or superadmin access;
- active business/user status where implemented.

## Agent Guidance

Agents should not store raw user passwords.

Preferred public Agent API flow:

- registered `agent_clients`;
- sandbox-first access;
- tenant-bound scoped tokens;
- explicit scopes such as `audit:read`, `reviews:draft`, `finance:read`, `approvals:create`, `publish:request`;
- capability allowlists;
- per-client and per-scope rate limits;
- revocation, cooldown, and suspension;
- action ledger and approval trace.

Status: `beta/internal` for the current Agent API security foundation; `gap` for a complete public product-wide agent-token system.
The minimal contract is published at `/api/agent-api/openapi.json`.
The root-level `/localos-agent-openapi.json` alias remains available for static discovery.

See also [Agent API Security Model](../agents/security-model.md).

## Agent API Keys

The first technical foundation uses `agent_clients`.

Creation:

```http
POST /api/agent-api/clients
Authorization: Bearer <superadmin_session_token>
Content-Type: application/json
```

The response returns `agent_key` once. Store it securely.

Usage:

```http
X-LocalOS-Agent-Key: <agent_key>
```

or:

```http
Authorization: Bearer <agent_key>
```

Current behavior:

- new clients are forced to `sandbox` even if `live` is requested;
- scopes are checked before agent actions;
- denied attempts are written to `agent_action_ledger`;
- high-risk direct actions are blocked and should be represented as approval requests.

## Agent Self-Test

After a sandbox client receives `agent_key`, run:

```bash
curl -s -X POST "https://localos.pro/api/agent-api/self-test" \
  -H "X-LocalOS-Agent-Key: $LOCALOS_AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "sandbox onboarding",
    "checks": ["auth", "scopes", "ledger"]
  }'
```

Expected result:

- key is valid or rejected with a structured error;
- status and allowed scopes are returned;
- a safe `agent_api_self_test` event appears in `agent_action_ledger`;
- no business action is executed.
