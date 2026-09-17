# Integrations

## Current Integrations

### Google Business Profile

Status: `beta / Google Basic API Access approved`

Current review context:

- project: `localos-gbp` (`649313441761`);
- agency account: `info@localos.pro`;
- approved support thread: `1-0494000040762`, approved 2026-09-03;
- submitted request: `6-7241000041686`, submitted 2026-09-01;
- approved quota: `300 QPM`;
- applicant verified profile for the active request: `LocalOS`;
- exact company website for the active request: `https://localos.pro/`;
- earlier response in the same support thread rejected the application because the submitted URL did not exactly match the public Business Profile URL;
- first managed verified client profile: `Веселая расческа`, Проспект Энгельса, 154;
- the new OAuth client is installed in production and server-side OAuth URL
  smoke passed on 2026-09-04; one real business OAuth connection and read-only
  sync still need to pass before external writes are treated as live.

Public positioning policy: describe LocalOS as integrating with Google Business
Profile APIs only. Do not state or imply a Google partnership, sponsorship, or
endorsement without separate written approval from Google.

Setup runbook: [`docs/GOOGLE_BUSINESS_PROFILE_LOCALOS_SETUP.md`](./GOOGLE_BUSINESS_PROFILE_LOCALOS_SETUP.md)

Confirmed endpoints:

- `GET /api/google/oauth/authorize`
- `GET /api/google/oauth/callback`
- `GET /api/business/<business_id>/google/status`
- `GET /api/business/<business_id>/google/locations`
- `POST /api/business/<business_id>/google/bind-location`
- `POST /api/business/<business_id>/google/sync`
- `POST /api/business/<business_id>/google/publish-review-reply`
- `POST /api/business/<business_id>/google/publish-post`

Publishing must require explicit user approval in product flows.
Direct publish endpoints reject requests without an explicit `approved: true` payload.

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
