# LocalOS Use Cases

## 1. Improve a Map Listing

Status: `available`

Use when a business wants to understand why a card is not converting well.

LocalOS can parse or read card data, show audit findings, prepare recommendations, and create a public audit page.

## 2. Optimize Services

Status: `available`

Use when service names and descriptions are too vague, noisy, or weak for search.

LocalOS can generate safer service wording with industry patterns and beauty-specific guardrails where applicable.

## 3. Reply to Reviews

Status: `available`

Use when a business needs short, controlled reply drafts.

LocalOS generates drafts. Publishing to external systems should require approval.

## 4. Generate News and Posts

Status: `available`

Use when map cards or content plans need regular updates.

LocalOS can generate drafts manually, through content plans, and through card automation flows.

## 5. Start Financial Tracking

Status: `available`

Use when a local business needs a first operating picture: revenue, expenses, margin, break-even, loading, no-shows, rebooking, workplaces.

LocalOS supports manual entry, file import, KPI thresholds, period history, recommendations, and CRM adapter scaffolding.

## 6. Connect External Map Accounts

Status: `beta`

Use when a business wants LocalOS to read or publish through external map systems.

Confirmed code includes external account storage, Google Business Profile OAuth, location binding, sync, Google publish endpoints, Yandex sync/admin endpoints, and 2GIS sync/admin endpoints. Contract stability varies by provider. Google Business Profile remains `beta / Google approval pending`.

## 7. Manage Multiple Locations

Status: `available`

Use when a network needs location-level diagnostics, not only network-level marketing.

LocalOS supports networks, locations, metrics, and network dashboards.

## 8. Find Partnership Opportunities

Status: `beta`

Use when a business wants nearby partners and supervised outreach.

LocalOS supports lead import, geo-search, lead parsing, audit, service/audience matching, map and website contact enrichment, public signal collection, founder-led draft sequences, approval, controlled delivery, stop-on-reply, and outcome tracking.

The sender is explicit: the business may speak for itself after completing its sender profile, or LocalOS may transparently represent the business through `localos_for_partner`. Matching still works when the business sender profile is incomplete; only the `partner_business` campaign is blocked.

Telegram and email are automatic only when a scoped sender account, permission, direct-send capability and reply sync are ready. WhatsApp, MAX, VK, SMS and other channels are manual until verified adapters exist.

See [LocalOS Outreach System](OUTREACH_SYSTEM.md).

## 9. Run AI Agents for Client Communication

Status: `beta`

Use when a business wants AI-assisted Telegram or WhatsApp conversations.

Current webhooks can receive messages and send responses through configured business channels. Policies, escalation, and production readiness must be checked per business.

## 10. Recalibrate Industry Patterns

Status: `available/internal`

Use when LocalOS learns from successful businesses and proposes new service/news/review patterns.

Pattern proposals require superadmin human-in-the-loop approval before activation.

## 11. Build Supervised AI Agents

Status: `beta`

Use when a business or operator wants repeatable automation with approvals, connection checks, billing, and audit.

LocalOS supports agent creation, compiled workflow previews, provider route selection, datahub sources, connector activation gates, run journals, approval queues, billing ledgers, and controlled execution through LocalOS/OpenClaw boundaries. Agents must not bypass approval for external sends, publications, payments, destructive changes, or third-party actions on behalf of a business.

Every account should expose a starter gallery of 10 popular supervised examples:
owner digest to Telegram, negative review reply drafts, card posts from signals,
service SEO cleanup, partnership outreach drafts, competitor website monitoring
through browser use, Google Sheets leads to Telegram, WhatsApp/Telegram FAQ
mining, finance import assistance, and tomorrow bookings checks. These are
inactive draft/templates until the user reviews, connects required services and
creates a real agent.

## 12. Monitor Parser Reliability

Status: `available/internal`

Use when map data refreshes fail, hit captcha, return partial payloads, or need safe retry decisions.

LocalOS tracks parse queue state, failure taxonomy, captcha and retry signals, TTL/DLQ handling, proxy health, provider cost settlement boundaries, and refresh recovery actions. Recovery flows are explicit and do not silently mutate external providers.
