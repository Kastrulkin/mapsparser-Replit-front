# What Is LocalOS

LocalOS helps local businesses become more profitable. It connects visibility, trust, services, reviews, posts, partnerships, finances, and repeatable execution into one practical path to growth.

The product goal is to help a business:

- attract more customers;
- increase average ticket;
- grow repeat sales;
- track revenue, costs, occupancy, and margin;
- understand what to do today, in 7 days, and regularly.

It is not only a map SEO tool. In the current codebase LocalOS includes:

- public card audits and map diagnostics;
- services and SEO wording optimization;
- review reply drafts, manual publish workflows, and review history sync;
- news, social post drafts, and network-aware content-plan operations;
- finance onboarding, KPI tracking, imports, and CRM adapter scaffolding;
- Telegram control surface and notifications;
- Google Business Profile OAuth, location binding, sync, and publishing endpoints;
- external account storage for map integrations;
- partnership prospecting, shortlist management, supervised outreach, and delivery/reaction tracking;
- AI agent webhooks for Telegram and WhatsApp;
- Agent cockpit, compiled workflows, provider routes, run journals, billing ledgers, and approval queues;
- OpenClaw / Action Orchestrator integration with LocalOS policy, audit, recovery, and human-in-the-loop boundaries;
- Apify-backed Google/Apple/Yandex/2GIS parsing paths and parser reliability controls;
- network dashboards, network-wide reviews, and multi-location content planning;
- admin-managed industry patterns and prompts.

## Who It Helps

- Owners and managers of local service businesses.
- Small networks with multiple locations.
- Specialists who manage map listings, content, reviews, or local SEO for clients.
- Internal and external AI agents that need a safe operating layer around local-business actions.

## Core Promise

LocalOS turns scattered local-business work into supervised workflows:

- find what is weak;
- prepare a concrete fix;
- ask for approval when the action affects customers, money, public content, or external systems;
- apply or track the change;
- measure what changed after the next data update.

## Current Product Scope

Confirmed areas:

- map/card audits;
- services, reviews, news, public materials, and content-plan workflows;
- finance dashboard and import pipeline;
- partnerships and prospecting workspace;
- Telegram and WhatsApp AI-agent entrypoints;
- Google Business Profile OAuth, sync, location binding, and publish endpoints;
- Yandex and 2GIS sync/admin endpoints.
- AI-agent builder/cockpit, compiled workflow runtime, connector route selection, run observability, approval queues, and billing ledgers.
- supervised outreach through shortlist selection, draft approval, capped send batches, manual delivery status, and inbound reaction tracking.
- parser reliability controls including proxy health gating, captcha retry caps, TTL/DLQ handling, and failure taxonomy.

Not confirmed as a public contract:

- full MCP server;
- complete public OpenAPI spec for all endpoints;
- automatic external publishing without approval;
- payments initiated by agents.

## Recent Product Additions

The last three months of development shifted LocalOS from a card-audit tool toward a supervised operating system for local businesses:

- agent workflows now use a compiled plan model with explicit capabilities, provider routes, connection preflight, versioning, preview runs, run journals, and approval queues;
- OpenClaw is treated as the execution boundary, while LocalOS owns policy, human approval, billing, audit, support export, and recovery flows;
- Google Business Profile support now covers OAuth, status, location selection, sync, review-reply publishing, and post publishing. A repeat Basic API Access application for project `localos-gbp` was submitted on 18 July 2026 using the verified managed client profile «Веселая расческа»; the integration remains `beta / Google review pending` until approval and a live publish proof;
- outreach now includes lead sourcing/import, shortlist decisions, message drafts, approval, capped send batches, delivery tracking, and reaction/outcome classification;
- content planning gained network modes, weekly/location filters, bulk actions, learning metrics, and quality signal prioritization;
- finance gained onboarding analytics, KPI history, partial-data handling, CRM adapter scaffolding, average-ticket/upsell views, and approved apply flows for agents;
- Telegram gained guest/client control flows, production proxy routing, refresh/retry commands, approvals, and agent binding guardrails;
- parsing gained Apify-backed sources, proxy/captcha controls, retry caps, task TTL/DLQ, queue monitoring, and clearer failure classes.

See [Documentation Gaps](DOCUMENTATION_GAPS.md).
