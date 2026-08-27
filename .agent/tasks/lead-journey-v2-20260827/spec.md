# Task Spec: lead-journey-v2-20260827

## Metadata
- Task ID: lead-journey-v2-20260827
- Created: 2026-08-27
- Repo root: /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре

## Guidance sources
- AGENTS.md
- README.md
- DESIGN.md
- agents/autonomous_development_brief.md
- docs/LEAD_JOURNEY_PRODUCT_UX_ARCHITECTURE.md
- docs/LEAD_JOURNEY_IMPLEMENTATION_PLAN_V2.md

## Original objective
Реализовать LEAD_JOURNEY_IMPLEMENTATION_PLAN_V2.md полностью: четыре детерминированных flow, post-auth continuity, content journey, административный мастер, Paths of Growth IA, block-level access, Mini App parity, telemetry, tests and safe rollout.

## Acceptance criteria

### AC1 — Four canonical flows
- Backend, database constraints, analytics and shared frontend types accept exactly `influencer`, `partnership`, `maps`, `content` plus the existing internal `upgrade` action flow where applicable.
- `CONTENT_JOURNEY_ENABLED` independently disables content claims and commands.
- Existing rows and legacy journeys remain readable.

### AC2 — Deterministic creation and public experience
- New admin-created journeys require `selected_flow` and a matching safe preview opportunity.
- The generated link opens the selected flow without asking the client to choose again.
- Other flows may be shown only as secondary discovery.
- Public payloads do not expose private contacts, complete outreach copy, paid full content or arbitrary redirects.

### AC3 — Auth continuity
- Guest registration, email verification and existing-user login preserve the token and selected flow.
- Claim is idempotent and tenant-safe.
- Successful claim opens the allowlisted workspace with `journey_action=<id>` instead of the generic dashboard/Today screen.
- Expired, revoked, mismatched and transient-failure states have explicit recovery behavior.

### AC4 — Content vertical
- Content uses existing content-plan, item, draft, calendar and supervised publication domains.
- A content journey can progress from safe preview to prepared/reviewed draft, calendar handoff, publication record, result and next cycle.
- Domain update and action transition are atomic.
- External publication is never implied or performed without the existing approval/preflight boundary.

### AC5 — Admin journey builder
- Superadmin can select a lead/business, one flow and a matching example, preview public/auth/paid states, create a versioned expiring link, copy the prepared message and revoke the link without SQL.
- Non-superadmin access is denied.
- The builder shows lifecycle, last event, current step and blocker.

### AC6 — Growth-path information architecture
- Authenticated product includes a Paths of Growth surface with Maps, Content, Influencers and Partnerships.
- Each path shows lifecycle, opportunity/blocker/result and one dominant CTA.
- Active/due/blocked journey work outranks discovery.
- Direct legacy URLs remain functional.

### AC7 — Block-level access
- Shared access states cover available, registration, payment, setup, approval and unavailable.
- Title, value, lock reason and CTA stay readable while representative preview may be softened.
- Backend authorization remains authoritative; CSS blur is not an access control.
- The four growth paths use the shared block access model before any route-wide gate is removed.

### AC8 — Navigation and cross-area exploration
- Primary navigation is grouped as Today, Growth paths, Results and More on web, with equivalent order in Mini App.
- A user may open other eligible areas without losing the current journey.
- Returning to Today restores the canonical next action.

### AC9 — Web/Mini App parity and telemetry
- Both surfaces render the same action identity/version/status/commands contract and deep-link to a concrete action.
- Funnel events cover link open through result/next cycle/upgrade/subscription with flow, surface, journey and action dimensions.
- Orphan/stale/domain mismatch and redirect failures are observable.

### AC10 — Quality, security and rollout readiness
- Backend state-machine, transaction, idempotency, concurrency, tenant and public-field tests pass.
- Frontend targeted tests and production build pass.
- Browser acceptance covers four flows, auth continuity, cross-area exploration, narrow viewport and no console errors.
- Production migration requires backup; release is feature-flagged and rollback-safe.
- Existing unrelated user changes are preserved.

## Constraints
- PostgreSQL is runtime source of truth; schema changes only through a new Alembic migration after `20260827_001`.
- Do not edit the already-applied `20260826_add_lead_journeys.py` migration.
- Do not create a second CRM, lead table, content-plan system, map audit system or universal workflow builder.
- Do not auto-send outreach, auto-publish, auto-pay or bypass approval/preflight.
- Do not accept arbitrary redirect URLs from public tokens.
- Preserve current dirty-worktree changes, especially ContentPage/media publication work.
- No production data mutation without explicit user approval; production schema migration requires backup.
- Existing direct routes remain compatible during navigation rollout.

## Non-goals
- Removal of old routes in this release.
- User-configurable workflows.
- Autonomous external publishing or outreach.
- Replacing existing creator, partnership, map or content domain tables.
- Automatic paywall opening.

## Verification plan
- Build: frontend production build in tmux; Python compile/import checks.
- Unit tests: lead journey service/API, auth resolver helpers, public page, action UI, navigation/access components.
- Integration tests: migration constraints, claim/command transactions, domain projections, stale/idempotency and tenant isolation.
- Lint/static: git diff check, targeted TypeScript/Python checks available in repo.
- Manual/browser: selected public link, registration continuation, exact workspace focus, four Paths of Growth, block locks, Mini App viewport, console.
- Proof: record commands and results in `.agent/tasks/lead-journey-v2-20260827/` and run proof-loop validate/status plus an independent final verifier.
