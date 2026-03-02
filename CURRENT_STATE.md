# Current State (2026-03-02)

## Runtime
- Deployment model: Docker Compose
- DB runtime: PostgreSQL
- Server path: `/opt/seo-app`
- Main services: `app`, `worker`, `postgres`
- Primary domain: `localos.pro`

## Canonical docs
1. `README.md` (primary source of truth)
2. `AGENTS.md` (agent behavior policy)
3. `.cursor/rules/*.mdc` (active workflows)
4. `.cursor/docs/*.md` (short logs/templates)

## What was cleaned
- Replaced outdated SQLite/systemd-first active rule files with Docker/Postgres workflows.
- Normalized implementation/verification/simplification docs to compact current templates.
- Added canonical `AGENTS.md` with explicit priority and deployment policy.

## Operational policy
- Prefer partial deploys.
- Use Alembic for schema changes.
- Always back up DB before server migrations.
- Treat legacy SQLite details as archival only.

## OpenClaw Integration
- Phases 1–9 of the LocalOS ↔ OpenClaw integration roadmap are complete.
- Current production capabilities include:
  - action orchestration, policy, billing ledger, approval workflow
  - M2M callback receiver/outbox/retry/DLQ
  - diagnostics, incident snapshot/report, recovery report/history
  - unified audit timeline and event bundles
  - Telegram-first control panel with approvals
  - multi-channel routing with Telegram, WhatsApp and Maton bridge adapter

## Current Product Focus
- Next implementation track: supervised outreach for lead generation.
- Admin panel already contains an early `Поиск клиентов` section backed by Apify, but it is still a draft and not yet a full staged outreach pipeline.
- Planned outreach mode:
  - manual shortlist approval
  - manual lead selection
  - manual approval of first-message drafts
  - capped sends (start with 10/day)
  - learning from approved edits and reply outcomes

## Sprint 0 (Outreach foundation)
- In progress:
  - secure `admin_prospecting` endpoints (auth + superadmin-only)
  - switch Apify sourcing to Yandex-first actor `m_mamaev/yandex-maps-places-scraper`
  - move prospecting search to async jobs (`outreachsearchjobs`) instead of synchronous HTTP wait
- Startup migrations are now serialized by PostgreSQL advisory lock in `entrypoint.sh` to avoid `deadlock detected` on simultaneous `app` + `worker` restarts.

## Sprint 1 (Outreach shortlist)
- Transitional staged UI is now built on top of existing `prospectingleads`.
- Candidate filtering is available by:
  - category
  - city
  - rating
  - reviews count
  - website / phone / email / messengers presence
- First manual review step is in place:
  - `В shortlist`
  - `Отклонить`

## Sprint 1.5 / Sprint 2A (Outreach contact selection)
- `ProspectingManagement` now includes a dedicated `Отбор для контакта` stage.
- Leads in `shortlist_approved` can be explicitly moved to:
  - `selected_for_outreach`
- After selection, superadmin can manually confirm the first contact channel:
  - `telegram`
  - `whatsapp`
  - `email`
  - `manual`
- Confirmed channel moves the lead to:
  - `channel_selected`
- Transitional runtime schema for this stage is now guaranteed in production:
  - `prospectingleads` exists
  - `selected_channel` column exists
  - current Alembic runtime revision on server is based on `20260302_003`

## Parsing runtime hardening
- Yandex service sync now rejects editorial/listing payloads (for example, "Хорошее место" collections and district/street подборки) instead of writing them into `userservices`.
- Added explicit human resume endpoint after captcha:
  - `POST /api/business/<business_id>/parse-resume`
- Production cleanup already applied for previously polluted services in:
  - `Новамед`
  - `Оливер`
