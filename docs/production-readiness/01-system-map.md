# LocalOS system map — audit working record

Source baseline `30262a5b`. References: `README.md`, `PRODUCT.md`, `AGENTS.md`, `docker-compose.yml`, `docs/LOCALOS_AGENT_ARCHITECTURE_V1.md`. Runtime checks remain incomplete.

## Product and users

LocalOS helps local business owners/managers, local SEO specialists and multi-location networks turn card/review/content/finance/partnership signals into reviewed actions. A successful journey ends with an observable result or a clear recoverable next action, not merely creation of an internal object. Superadmin is a separate platform scope; business and network memberships are tenant boundaries.

## Components, flow and trust boundaries

```mermaid
flowchart TD
    U[Owner / manager / network member] -->|HTTPS session / tenant selection| UI[React SPA / Telegram Mini App]
    UI -->|Untrusted request| API[Gunicorn / Flask app]
    TB[Telegram owner bot] -->|Bound identity and scope| CORE[Operator policy / approval / billing / audit]
    API --> AUTH[Session + business / network access guards]
    AUTH --> DOMAIN[Cards / services / reviews / content / finance / partnerships]
    DOMAIN --> CORE
    AUTH --> PG[(PostgreSQL authoritative data)]
    DOMAIN --> PG
    CORE --> PG
    CORE --> EXEC[OpenClaw / Action Orchestrator execution boundary]
    W[Worker / operator-worker] -->|Claim / retry / recover| PG
    W --> EXEC
    API --> REDIS[(Redis rate limiting / transient state)]
    EXEC -->|Explicit approved capability| EXT[Maps / social / messaging / LLM / payment providers]
    EXT -->|Untrusted callback / retrieved content| IN[Webhook / import / retrieval ingress]
    IN --> AUTHIN[Provider identity / signature / validation]
    AUTHIN --> DOMAIN
    MIG[Explicit migration owner] -->|Alembic schema changes| PG
```

Provider content/model output are data, not authorization. Signing callbacks does not authorize arbitrary business actions. Dangerous tools must enforce human approval, scoped identity, billing/policy and audit outside prompts.

## Runtime inventory

| Component | Responsibility / source | Important state |
| --- | --- | --- |
| Flask app | `src/main.py`, `src/api/`, `src/legacy_routes/`; HTTP API and SPA | Sessions, request authorization, domain transactions |
| React frontend/public site | `frontend/src/App.tsx`, routes and feature modules; Vite/TypeScript | Browser session/business selection, draft/review state |
| Main worker | `src/worker.py`; parser/jobs and recovery | PostgreSQL claims; `FOR UPDATE SKIP LOCKED` path |
| Operator worker/bot | Compose services and Operator/Telegram modules | Scope-bound commands, confirmations, action journal |
| PostgreSQL 16 + pgvector | Canonical relational runtime database, 168 tracked Alembic version files | Tenants, memberships, business data, approvals, queue and audit |
| Redis | Shared limiter/transient service | Not the durable business source of truth |
| Upload/debug/audio files | Runtime writable storage | Potential private content; separate from read-only source |
| External execution | OpenClaw/orchestrator and provider clients | Timeouts, retries, uncertainty, consent and provider IDs |

Tracked inventory: 555 files under `src`, 408 under `tests`, 648 under `frontend`, 239 under `scripts`. These are file counts, not test coverage.

## Five critical journeys selected for measurement

1. **Access and tenant selection:** sign in → select permitted business → dashboard; expired/inactive/foreign-tenant denial. `auth_admin.py`, `auth_system.py`, `core/auth_helpers.py`.
2. **Service menu change:** view current services → compression/group proposal → review → apply once → see preserved archive/new menu; concurrent apply and rollback integrity. `src/api/services_api.py`.
3. **Finance import:** parse/preview synthetic import → duplicate validation → explicit apply → KPI/history; no cross-tenant writes or partially committed batch. `src/api/finance_api.py`.
4. **Content plan to reviewed draft:** select business → generate/mock draft → review → approval → safe provider stub outcome; no publish merely from preview. `content_plans` / `social_posts` APIs and services.
5. **Operator governed action:** request → scoped proposal → preflight/review → explicit confirmation → journal result, including denied/cancelled/provider-timeout paths. `src/api/operator_api.py`, agent/orchestrator services.

Supervised outreach, reviews and Telegram are mandatory adjacent coverage, including no-send and stop-on-reply. They are not omitted because only five journeys receive the primary performance table.

## Sensitive data and irreversible edges

Credentials, session tokens, provider keys, business finances, private knowledge, uploads, contacts and messages require scoped access and redaction. Publishing, outreach sends, payments, access changes, destructive/bulk actions and provider writes need explicit approval. Do not use real customer data for this audit/demo.

## Deployment reality / unresolved gaps

Compose defines app, worker, operator-worker, Telegram, PostgreSQL, Redis and ancillary services. Base Compose bind-mounts host code over image contents, so image identity alone is not a release attestation. The isolated staging override removes code/env mounts and suppresses integrations. Alembic has an advisory lock, but multiple startup actors remain a configuration concern. These are audit findings, not instructions to mutate production now.
