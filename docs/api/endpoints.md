# API Endpoints

This is a practical catalog of confirmed routes. It is not a full OpenAPI contract.

All examples assume:

```http
Authorization: Bearer <auth_token>
```

## Auth and User

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/auth/register` | `available` | Email/password registration. |
| `POST` | `/api/auth/login` | `available` | Returns session token. |
| `GET` | `/api/auth/me` | `available` | Current user. |
| `POST` | `/api/auth/logout` | `available` | Logout. |
| `POST` | `/api/auth/verify-email` | `available` | Email verification. |
| `POST` | `/api/auth/set-password` | `available` | Password setup by token. |

## Card and Audit

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/analyze` | `available` | Queue/analyze map card. |
| `POST` | `/api/analyze-card-auto` | `available` | Automated card analysis. |
| `GET` | `/api/business/<business_id>/parse-status` | `available` | Parse status. |
| `GET` | `/api/business/<business_id>/map-parses` | `available` | Map parse snapshots. |
| `GET` | `/api/map-report/<parse_id>` | `available` | Map report data. |
| `GET` | `/api/business/<business_id>/card-audit` | `available` | Progress API blueprint. |
| `GET` | `/api/public/report-offer/<slug>` | `available` | Public audit/offer payload. |

## External Accounts and Map Data

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/business/<business_id>/external-accounts` | `available` | List connected accounts. |
| `POST` | `/api/business/<business_id>/external-accounts` | `available` | Add account. Approval required for credentials. |
| `DELETE` | `/api/external-accounts/<account_id>` | `available` | Destructive. |
| `POST` | `/api/business/<business_id>/external-accounts/test` | `available` | Test account. |
| `GET` | `/api/business/<business_id>/external/reviews` | `available` | Stored external reviews. |
| `GET` | `/api/business/<business_id>/external/posts` | `available` | Stored external posts/news. |
| `GET` | `/api/business/<business_id>/external/summary` | `available` | External account summary. |

## Services

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/services/list` | `available` | Service list. |
| `POST` | `/api/services/optimize` | `available` | Generate SEO suggestions. |
| `POST` | `/api/services/add` | `available` | Create service. Approval recommended. |
| `PUT` | `/api/services/update/<service_id>` | `available` | Update service. Approval required if agent-driven. |
| `DELETE` | `/api/services/delete/<service_id>` | `available` | Destructive. |

## Reviews

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/reviews/reply` | `available` | Generate reply draft. |
| `POST` | `/api/review-replies/update` | `available` | Update stored reply. |
| `POST` | `/api/business/<business_id>/google/publish-review-reply` | `beta` | External publish; approval required. |

## News and Content Plans

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/news/generate` | `available` | Generate news draft. |
| `POST` | `/api/news/approve` | `available` | Approve generated news. |
| `GET` | `/api/news/list` | `available` | List news. |
| `POST` | `/api/news/update` | `available` | Update news. |
| `POST` | `/api/news/delete` | `available` | Destructive. |
| `GET` | `/api/content-plans/context` | `available/beta` | Content plan context. |
| `GET` | `/api/content-plans` | `available/beta` | List plans. |
| `POST` | `/api/content-plans/generate` | `available/beta` | Generate plan. |
| `POST` | `/api/content-plans/items/<item_id>/generate-draft` | `available/beta` | Draft item. |
| `POST` | `/api/content-plans/items/<item_id>/create-news` | `available/beta` | Create news from item. |
| `POST` | `/api/business/<business_id>/google/publish-post` | `beta` | External publish; approval required. |

## Finance

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/finance/dashboard` | `available` | Supports `business_id`, `from`, `to`, `range=all`. |
| `POST` | `/api/finance/manual-entry` | `available` | Write finance data; approval required for agents. |
| `POST` | `/api/finance/recalculate` | `available` | Recalculate snapshot. |
| `GET` | `/api/finance/data-quality` | `available` | Missing/approximate data. |
| `GET` | `/api/finance/recommendations` | `available` | Red zones and actions. |
| `GET/PUT` | `/api/finance/thresholds` | `available` | KPI norms. |
| `POST` | `/api/finance/thresholds/reset` | `available` | Reset KPI norms. |
| `GET/POST` | `/api/finance/actions` | `available` | Action checklist. |
| `GET` | `/api/finance/history` | `available` | Period history. |
| `GET` | `/api/finance/impact` | `available` | Action impact. |
| `POST` | `/api/finance/import-preview` | `available/beta` | Preview import. |
| `POST` | `/api/finance/import-file` | `available/beta` | Import file after preview. |
| `GET` | `/api/finance/imports` | `available` | Import history. |
| `GET` | `/api/finance/crm/providers` | `beta` | Providers. |
| `POST` | `/api/finance/crm/preview` | `beta` | Sync preview. |
| `POST` | `/api/finance/crm/sync` | `beta` | Sync. Approval required. |

## Agent API Security

Status: `beta/internal`.

These endpoints implement the first Agent API security foundation. They are not a full public MCP/API product yet.

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/agent-api/security/policy` | `beta/internal` | Returns current Agent API security policy summary. |
| `POST` | `/api/agent-api/clients` | `beta/internal` | Superadmin creates a sandbox agent client. The key is returned once. |
| `GET` | `/api/agent-api/clients` | `beta/internal` | Superadmin lists registered agent clients without key material. |
| `POST` | `/api/agent-api/approvals/request` | `beta/internal` | Agent records a pending human approval request. Uses `X-LocalOS-Agent-Key`. |
| `GET` | `/api/agent-api/ledger` | `beta/internal` | Superadmin lists recent agent action ledger events. |

Agent keys may also be passed as `Authorization: Bearer <agent_key>`, but `X-LocalOS-Agent-Key` is preferred.

New agent clients are created as `sandbox` by default. Direct publish, payment, customer messaging, destructive, or external-system actions remain blocked and must go through approval.

## Partnerships and Prospecting

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/partnership/leads/import-links` | `beta` | Import links. |
| `POST` | `/api/partnership/leads/import-file` | `beta` | Import file. |
| `POST` | `/api/partnership/geo-search` | `beta` | Geo search. |
| `GET` | `/api/partnership/leads` | `beta` | Lead list. |
| `PATCH` | `/api/partnership/leads/<lead_id>` | `beta` | Update lead. |
| `POST` | `/api/partnership/leads/<lead_id>/parse` | `beta` | Parse lead. |
| `POST` | `/api/partnership/leads/<lead_id>/audit` | `beta` | Lead audit. |
| `POST` | `/api/partnership/leads/<lead_id>/match` | `beta` | Match services. |
| `POST` | `/api/partnership/leads/<lead_id>/draft-offer` | `beta` | Draft offer. |
| `GET` | `/api/partnership/drafts` | `beta` | Drafts. |
| `POST` | `/api/partnership/drafts/<draft_id>/approve` | `beta` | Approval. |
| `POST` | `/api/partnership/send-batches` | `beta/internal` | Create send batch. |
| `POST` | `/api/partnership/send-batches/<batch_id>/approve` | `beta/internal` | Approve batch. |

## Admin and Patterns

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/admin/prompts` | `internal` | Prompt admin. |
| `PUT` | `/api/admin/prompts/<prompt_type>` | `internal` | Update prompt. |
| `POST` | `/api/admin/industry-patterns/recalibrate` | `internal` | Creates proposals. |
| `GET` | `/api/admin/industry-patterns/proposals` | `internal` | List proposals. |
| `POST` | `/api/admin/industry-patterns/proposals/<proposal_id>/decision` | `internal` | Approve/reject/rework. |
| `POST` | `/api/admin/industry-patterns/versions/<version_id>/rollback` | `internal` | Rollback. |

## Webhooks

| Method | Path | Status | Notes |
| --- | --- | --- | --- |
| `POST|GET` | `/api/webhooks/whatsapp` | `beta` | WABA inbound. |
| `POST` | `/api/webhooks/telegram` | `beta` | Telegram inbound. |
| `POST` | `/api/webhooks/telegram/<bot_token>` | `beta` | Token URL variant. |

## Not Yet Documented as Public API

- MCP tool server.
- Agent-scoped tokens.
- Full OpenAPI spec.
- Complete external publish abstraction across Yandex, 2GIS, Google.
