# Integrations

## Current Integrations

### Google Business Profile

Status: `beta`

Confirmed endpoints:

- `GET /api/google/oauth/authorize`
- `GET /api/google/oauth/callback`
- `POST /api/business/<business_id>/google/publish-review-reply`
- `POST /api/business/<business_id>/google/publish-post`

Publishing must require explicit user approval in product flows.

### Yandex Business

Status: `internal/beta`

Confirmed endpoints include admin sync routes:

- `POST /api/admin/yandex/sync/<network_id>`
- `POST /api/admin/yandex/sync/business/<business_id>`
- `GET /api/admin/yandex/sync/status/<sync_id>`

Public, stable write APIs are not documented in this repository.

### 2GIS

Status: `internal/beta`

Confirmed endpoint:

- `POST /api/admin/2gis/sync/business/<business_id>`

Public, stable write APIs are not documented in this repository.

### Telegram

Status: `available/beta`

Confirmed areas:

- Telegram bind endpoints;
- owner bot/control surface described in README;
- AI-agent Telegram webhook endpoints;
- business-level Telegram bot token support.

### WhatsApp Business API

Status: `beta`

Confirmed endpoint:

- `POST|GET /api/webhooks/whatsapp`

Uses WABA phone id and access token stored on the business. Production policy must define escalation and limits before autonomous replies.

### CRM for Finance

Status: `beta/planned`

Confirmed finance CRM adapter endpoints:

- `GET /api/finance/crm/providers`
- `POST /api/finance/crm/connect`
- `GET /api/finance/crm/status`
- `POST /api/finance/crm/preview`
- `POST /api/finance/crm/sync`

Current provider layer includes a mock/demo contract. Real YCLIENTS/Altegio production connection requires provider credentials and contract validation.

## Gaps

- No single public integrations catalog endpoint.
- No complete OpenAPI file for all production APIs.
- No confirmed MCP server contract in repository docs.
