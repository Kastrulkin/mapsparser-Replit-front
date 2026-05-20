# Human Approval Policy

LocalOS is designed for supervised automation. Agents may prepare, preview, and recommend. They must not perform high-impact actions without approval.

## Approval Required

Always require human approval for:

- publishing posts/news to Google, Yandex, 2GIS, social channels, or other public systems;
- publishing review replies;
- changing service names, descriptions, prices, or categories in external cards;
- sending customer, partner, or prospect messages;
- creating or approving outreach batches;
- payment, billing, tariff, or credit changes;
- destructive actions: delete, disable, rollback, bulk update;
- external account credential changes;
- actions made on behalf of the business in a third-party system;
- activating industry patterns from recalibration proposals.

## Approval Recommended

Require approval unless a narrow business policy explicitly allows automation:

- booking creation/update/cancel;
- finance imports after preview;
- CRM sync;
- AI-agent customer replies where the answer contains commitments, pricing, availability, medical/legal claims, or complaint resolution.

## Read-Only Actions

Usually do not require approval:

- reading dashboard data;
- summarizing audits;
- listing services, reviews, posts, finance KPIs, or leads;
- generating a draft without applying it.

## Paid Action Consent

Paid actions are separate from approval. A user may consent to spend credits for an action, but that does not approve external publication, sending, payment, destructive changes, or third-party writes.

Paid action classes are defined in [LocalOS Operator](localos-operator.md) and [Tool registry](tool-registry.md):

- `paid_compute`: AI/model work such as review reply drafts, news generation, social post drafts, service optimization, and content plans.
- `paid_external`: external provider or parser work such as Apify map refresh, competitor parsing, or enrichment.

Business-level consent modes:

- `ask_each_time`: explain cost and ask before each paid action.
- `auto_with_limits`: allow repeated paid actions only within configured limits.
- `disabled`: block this paid action class.

Recommended limits:

- max credits per action;
- max credits per day;
- max credits per month;
- low balance warning threshold.

After each paid execution, LocalOS should show the actual charge and write a ledger/audit event.

## Manual External Publication

When external provider write support is unavailable, LocalOS must stop at draft/manual assist.

For map review replies today, LocalOS may:

- generate and store reply drafts;
- show copy buttons;
- open a provider screen when a safe link is available;
- let a user mark an item as manually published.

LocalOS must not claim it published replies to Yandex, Google, 2GIS, or another map provider unless that provider write flow is implemented, verified, documented, and governed by approval policy.

## Approval Record

A safe approval record should include:

- actor and approver;
- business id;
- capability;
- source input;
- proposed output;
- final approved output;
- timestamp;
- idempotency key or trace id;
- delivery result if an external action follows.

## Agent Rule

If an agent is unsure whether approval is required, it must stop at draft/preview and ask.

## Security Boundary

Approval is part of the security model, not just UX.

Agents should treat these as separate permissions:

- read data;
- create a draft;
- request approval;
- execute approved action;
- read audit trail.

Having permission to create a draft never implies permission to publish, message, pay, delete, or change external systems.

Current Agent API foundation records approval requests through `POST /api/agent-api/approvals/request`. It stores the request in `agent_action_ledger` with `status=pending_human`.

For the broader model, see [Agent API Security Model](security-model.md).
