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

Preferred future flow:

- scoped API tokens for agent integrations;
- capability allowlists;
- tenant-bound tokens;
- revocation and audit log.

Status: `gap` for a complete public agent-token system.
