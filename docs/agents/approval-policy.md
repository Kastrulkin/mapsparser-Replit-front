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
