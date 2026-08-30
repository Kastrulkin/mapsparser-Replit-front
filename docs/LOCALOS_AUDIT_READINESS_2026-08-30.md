# LocalOS audit readiness — 2026-08-30

## Scope and release decision

This document records the current evidence for the ten user scenarios and the
security gates requested for the LocalOS audit. It is deliberately stricter
than a smoke-test report: a scenario is marked complete only when the whole
requested path is exercised against the isolated staging backend.

Current decision: **not ready for production rollout**. Production was not
changed during this audit.

## Current staging baseline

- Isolated Docker Compose project: `localos-staging`.
- Synthetic PostgreSQL data and empty real-provider credentials.
- External sends and publications disabled.
- Latest completed browser run before the staging interruption: 41 passed,
  10 intentionally skipped, 0 failed across desktop, laptop and mobile.
- Latest journey projection health check: 5 active actions, 0 orphan actions,
  0 stale actions, 0 blocked actions, 0 missing journey links, 0 missing
  domain entities and 0 notification dedupe failures.
- The staging runtime is currently unavailable because Docker Desktop stopped
  after a storage I/O error while the host volume had about 1.9 GB free.

## Ten-scenario evidence matrix

| # | Scenario | Proven now | Missing or contradicted evidence | Status |
|---|---|---|---|---|
| 1 | New user — maps | Safe public preview, selected-flow continuity, registration, email verification, cookie session and redirect to the selected maps action | No current browser proof of the full `complete task → refresh → verified comparison → next week` cycle; provider failure recovery is not exercised end to end | Partial |
| 2 | New user — influencers | Safe public preview, registration continuity and redirect to the influencer workspace | No full browser proof of service-for-barter input, generated offer, paywall boundary, send/reply, placement and measured result | Partial |
| 3 | New user — partnerships | Safe public preview, registration continuity and redirect to the partnership workspace | `leads`, `blockers-summary` and `ralph-loop-summary` return HTTP 500 on staging because PostgreSQL compares `parsequeue.business_id` (`text`) with `prospectingleads.parse_business_id` (`uuid`) | Failed |
| 4 | New user — content | Safe public preview, registration continuity and redirect to the selected content action | No current browser proof of the whole facts form, draft, review, calendar, confirmed publication, result and next cycle | Partial |
| 5 | New user — automation | Safe preview; registration continuity; web and Mini App share the same action; configuration, preflight review, approval boundary and transition to run are exercised | The actual supervised run, result review and next-cycle transition are not exercised end to end | Partial |
| 6 | Existing owner — reviews | An unanswered review opens with a prepared draft, copy action and explicit manual-publication boundary; no runtime errors in the tested page | Confirmed provider publication is intentionally not executed on staging | Pass for safe/manual scope |
| 7 | Existing owner — finance | File preview, explicit import, and duplicate retry are exercised; second import produces two dedupe skips instead of duplicate accounting | Error-row correction and mixed valid/invalid file UX are covered indirectly, not by this staging browser suite | Pass for primary path |
| 8 | Network manager | Network aggregate, location switch, state restoration and 403 responses for foreign business/network scopes are exercised | No remaining primary-path gap found | Pass |
| 9 | Web ↔ Mini App | Shared action status, web-to-Mini-App continuity, idempotent replay, stale-version rejection and offline retry are exercised | The strongest proof uses the automation flow; every vertical is not independently repeated across both surfaces | Pass for shared contract |
| 10 | Admin creates journey | Selected flow, client preview, public privacy, link creation, revoke and HTTP 410 after revoke are exercised | Expiry and single-claim conflicts are proven by backend tests, not by browser E2E | Pass with backend support |

## Security gates

| Gate | Current evidence | Status |
|---|---|---|
| Browser auth and CSRF | Browser session uses `HttpOnly`, `Secure`, `SameSite=Lax`; unsafe cookie-authenticated requests require a matching CSRF header; browser E2E confirms no bearer token in `localStorage` | Pass |
| Tenant isolation | Network browser test and backend authorization tests reject foreign business and network scopes | Pass for tested scopes |
| Public journey links | Expiry, revocation, tenant reservation, single claim, allowlisted guest events and removal of full messages/contacts are covered by focused tests | Pass |
| Error redaction | Auth, public auth, progress, content voice, integrations and sales-room failures return safe errors; provider/SQL details stay server-side | Pass for audited routes |
| SSRF | Media downloads reject loopback, private/link-local destinations and unsafe redirects while retaining the configured proxy route | Pass |
| Upload content validation | Media and public sales-room uploads verify signatures and OpenXML structure instead of trusting extension/MIME | Pass |
| Approval boundaries | Existing audits and focused tests keep sends, publishing, payments and automation execution behind review/preflight/manual confirmation | Pass for audited actions |
| Dependency audit | Python audit reports no known vulnerabilities; npm production and full audits report zero vulnerabilities | Pass at current lockfiles |
| Accessibility | Axe on all five public journey previews, at desktop/laptop/mobile sizes, reports 0 critical but 2 serious color-contrast nodes per page | Failed |
| Secrets | Live Wordstat credentials still exist in ignored local environment files, and related credential material exists in Git history. Values are not copied into this report | Failed until provider rotation and history remediation decision |
| Static analysis | A new Semgrep auto-config run did not start because auto config and disabled metrics are incompatible; earlier results are not a durable current gate | Not proven |
| Container vulnerabilities | Trivy database download failed with a Docker storage I/O error before the image could be assessed | Not proven |
| ZAP baseline | The attempted rerun did not complete because Docker stopped | Not proven in current run |
| Journey monitoring | Health check covers orphan/stale/blocked actions, missing links/entities and notification dedupe failures; staging result was clean | Pass |

## Newly reproduced defects awaiting regression-test approval

1. Partnership query type mismatch affects three related endpoints. The
   minimal test package should execute each query against PostgreSQL and assert
   a successful empty or populated response without weakening tenant checks.
2. Public journey contrast fails the requested `zero serious/critical Axe`
   criterion in all five flows and all three target viewports. A shared
   accessibility regression should identify the common component before any
   design-token change.

## Required work before rollout

1. Obtain approval, add failing tests for the partnership and contrast defects,
   then obtain the separate fix approval required by the bug workflow.
2. Restore enough local disk capacity for Docker without deleting project or
   user data; restart only the isolated staging project.
3. Repair the proven defects and repeat the focused red-to-green tests.
4. Add the missing full-cycle browser coverage for maps, influencers, content,
   partnerships and the automation result/next-cycle stage.
5. Repeat Axe on authenticated workspaces, Semgrep with explicit local rules,
   Gitleaks with redaction, Trivy and ZAP baseline.
6. Rotate the exposed Wordstat credentials externally. Decide separately
   whether Git-history rewriting is acceptable; do not rewrite history as part
   of an ordinary application deployment.
7. Run the full 10-scenario suite, journey health check, backend security
   profile and frontend build/typecheck after all fixes.
8. Prepare a flag-by-flag rollout package. Do not deploy to production without
   a separate explicit authorization and a production database backup where a
   migration is involved.

