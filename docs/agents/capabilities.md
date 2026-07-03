# Agent Capabilities

This page is a machine-readable human guide. Status values: `available`, `beta`, `internal`, `planned`, `gap`.

## Capability Matrix

| Capability | Status | Primary endpoints | Approval |
| --- | --- | --- | --- |
| `card.audit` | `available` | `POST /api/analyze`, `GET /api/business/<business_id>/card-audit`, `GET /api/public/report-offer/<slug>` | Not for read; required for sending report externally |
| `card.external_accounts` | `available/beta` | `GET/POST /api/business/<business_id>/external-accounts`, `POST /api/business/<business_id>/external-accounts/test` | Required for credential changes |
| `services.optimize` | `available` | `POST /api/services/optimize`, `GET /api/services/list` | Required before applying/public publishing |
| `services.compress_menu` | `available` | `POST /api/services/compression/draft`, `PUT /api/services/compression/draft/<id>`, `POST /api/services/compression/draft/<id>/apply`, `POST /api/services/compression/draft/<id>/rollback` | Required before applying grouping/rollback |
| `services.manage` | `available` | `POST /api/services/add`, `PUT /api/services/update/<service_id>`, `DELETE /api/services/delete/<service_id>` | Required for create/update/delete |
| `reviews.reply_draft` | `available` | `POST /api/reviews/reply`, `POST /api/review-replies/update` | Required before publishing |
| `reviews.google_publish` | `beta` | `POST /api/business/<business_id>/google/publish-review-reply` | Required |
| `news.generate` | `available` | `POST /api/news/generate`, `POST /api/news/approve`, `GET /api/news/list` | Required for approval/publish |
| `content_plan.generate` | `available/beta` | `POST /api/content-plans/generate`, `POST /api/content-plans/items/<item_id>/generate-draft` | Required before external publish |
| `finance.dashboard` | `available` | `GET /api/finance/dashboard`, `GET /api/finance/data-quality`, `GET /api/finance/recommendations` | Not for read |
| `finance.manual_entry` | `available` | `POST /api/finance/manual-entry`, `POST /api/finance/recalculate` | Required if agent writes financial data |
| `finance.import` | `available/beta` | `POST /api/finance/import-preview`, `POST /api/finance/import-file` | Required after preview |
| `finance.crm_sync` | `beta` | `POST /api/finance/crm/preview`, `POST /api/finance/crm/sync` | Required for sync |
| `finance.transactions` | `available/internal` | `POST/PUT/DELETE /api/finance/transaction...` | Required, destructive for delete |
| `partnership.leads` | `beta` | `/api/partnership/leads...`, `/api/partnership/geo-search` | Required for bulk and destructive |
| `partnership.draft_offer` | `beta` | `POST /api/partnership/leads/<lead_id>/draft-offer` | Required before send |
| `partnership.send_batch` | `beta/internal` | `POST /api/partnership/send-batches`, `POST /api/partnership/send-batches/<batch_id>/approve` | Required |
| `industry_patterns.recalibrate` | `internal` | `POST /api/admin/industry-patterns/recalibrate`, proposal decision endpoints | Superadmin required |
| `ai_agent.webhooks` | `beta` | `POST /api/webhooks/telegram`, `POST|GET /api/webhooks/whatsapp` | Policy-based; escalation required for uncertain cases |
| `mcp.tools` | `gap` | None confirmed | N/A |
| `agent_api.security_model` | `beta/internal` | `GET /localos-agent-policy.json`, `GET /api/agent-api/security/policy`, `POST /api/agent-api/clients`, `POST /api/agent-api/approvals/request` | Required for high-risk actions |

## Capability Details

### `card.audit`

- Status: `available`
- What it does: analyzes a public map card or returns existing card audit data.
- When to use: first diagnosis, public audit generation, lead qualification.
- Inputs: map URL or `business_id`; optional language/scope.
- Output: audit data, public report offer, status.
- Limits: parser coverage depends on provider and available snapshot.
- Approval: required before sending audit to a customer or partner.
- Example: see [API examples](../api/examples.md#card-audit).

### `services.optimize`

- Status: `available`
- What it does: generates improved service names/descriptions and SEO/key coverage.
- When to use: card services are vague, noisy, duplicated, or missing key terms.
- Inputs: `business_id`, service rows, industry context, existing prompts.
- Output: suggestions, guardrail results, keyword scoring.
- Limits: beauty guardrails are industry-specific and must not be applied globally.
- Approval: required before applying to external cards.

### `services.compress_menu`

- Status: `available`
- What it does: creates and edits a draft that groups similar services, creates confirmed combined LocalOS services, and softly archives original rows.
- When to use: service lists are overloaded, duplicated, hard to scan, or contain many variants that should live inside one client-facing service.
- Inputs: `business_id`, saved `userservices`, user-edited groups, final names, categories, descriptions, prices and action choices.
- Output: draft grouping, diff, created service ids, archived source ids and rollback state.
- Limits: v1 changes only LocalOS `userservices`; it does not write grouped services to Yandex, Google, 2GIS or another external provider.
- Approval: required before apply and rollback.

### `reviews.reply_draft`

- Status: `available`
- What it does: drafts a review reply.
- When to use: new reviews, backlog cleanup, tone alignment.
- Inputs: review text, rating, business context, examples.
- Output: reply draft.
- Limits: must not invent facts or promise fixes not approved by the business.
- Approval: required before publishing.

### `news.generate`

- Status: `available`
- What it does: generates draft card news/posts.
- When to use: content plan, seasonal update, service explanation, card activity.
- Inputs: business id, context, topic/source data.
- Output: news draft and metadata.
- Limits: generated items may still require manual copy-paste depending on provider flow.
- Approval: required before publishing.

### `finance.dashboard`

- Status: `available`
- What it does: returns KPIs, quality score, recommendations, history, and source data.
- When to use: first financial diagnosis and monthly operating review.
- Inputs: `business_id`, `from`, `to` or `range=all`.
- Output: `kpis`, `data_quality`, `recommendations`, `period_history`, source rows.
- Limits: incomplete data returns `null` and explanations for some KPIs.
- Approval: not required for read.

### `partnership.draft_offer`

- Status: `beta`
- What it does: drafts partnership outreach based on lead/business context.
- When to use: supervised local partnership workflow.
- Inputs: lead id, channel, parsed lead context.
- Output: draft message/offer.
- Limits: uses transitional `prospectingleads` table.
- Approval: required before sending.

### `industry_patterns.recalibrate`

- Status: `internal`
- What it does: proposes new patterns from recent business data.
- When to use: monthly recalibration by superadmin.
- Inputs: source period and industry data.
- Output: pending proposals with examples, risk, confidence.
- Limits: proposals must not become active automatically.
- Approval: superadmin required.

### `agent_api.security_model`

- Status: `beta/internal`
- What it does: defines agent registration, scopes, sandbox mode, approval boundary, rate limits, abuse detection, webhook signing, and audit trail.
- When to use: before opening LocalOS API/MCP to third-party agents.
- Inputs: agent client identity, scopes, business tenant, action type, risk level.
- Output: allow, deny, cooldown, approval required, or manual review.
- Limits: this is a foundation for controlled access, not a fully public API/MCP implementation.
- Approval: required for high-risk and critical actions.
