# LocalOS audit readiness — 2026-08-30

## Scope and release decision

This document records the current evidence for the ten user scenarios and the
security gates requested for the LocalOS audit. It is deliberately stricter
than a smoke-test report: a scenario is marked complete only when the whole
requested path is exercised against the isolated staging backend.

Current decision: **not ready for production rollout**. Production was not
changed during this audit.

## Current staging baseline

- Docker Desktop remains unavailable after a storage I/O error, so the audit
  fallback runs the same application natively against an isolated PostgreSQL
  15 cluster on `127.0.0.1:15432` and the application on
  `127.0.0.1:18000`.
- The fallback database is migrated to `20260830_003`, uses pgvector `0.8.6`,
  contains only synthetic fixtures and has empty real-provider credentials.
- External sends, publications and asynchronous runs are disabled.
- Public smoke passes for maps, influencer, partnership, content and
  automation. After the isolated registration rerun, the journey health check
  reports 5 active actions, 0 orphan, stale or blocked actions, 0 missing
  links/entities and 0 notification dedupe failures.
- The initial full browser run completed with 39 passed, 10 intentional skips
  and 2 failures across desktop, laptop and mobile. Both causes were isolated:
  one was a staging relation lock caused by request-time DDL and the other was
  the same missing clean-schema column. After the schema fix, the partnership
  API passes in all three viewports (3/3). The public journey accessibility
  regression passes for all five flows in all three viewports (15/15).
- The current focused backend security/journey profile passes 117/117 tests.
  The narrower changed-path regression passes 15/15 tests. It covers
  browser-session security, tenant checks, safe public errors, journey
  transitions, upload signatures, media-download SSRF and pinned callback
  dispatch. Docker-backed callback integration tests remain unavailable while
  Docker Desktop is broken.

## Ten-scenario evidence matrix

| # | Scenario | Proven now | Missing or contradicted evidence | Status |
|---|---|---|---|---|
| 1 | New user — maps | Safe public preview, selected-flow continuity, registration, email verification, cookie session and redirect to the selected maps action | No current browser proof of the full `complete task → refresh → verified comparison → next week` cycle; provider failure recovery is not exercised end to end | Partial |
| 2 | New user — influencers | Safe public preview, registration continuity and redirect to the influencer workspace; the isolated native-staging rerun passed | No full browser proof of service-for-barter input, generated offer, paywall boundary, send/reply, placement and measured result | Partial |
| 3 | New user — partnerships | Safe public preview, registration continuity and redirect to the partnership workspace; `leads`, `blockers-summary` and `ralph-loop-summary` now return HTTP 200 on PostgreSQL staging across desktop/laptop/mobile | No full browser proof of mechanic selection, prepared and approved message, reply, launch, measured result and next cycle | Partial |
| 4 | New user — content | Safe public preview, registration continuity and redirect to the selected content action | No current browser proof of the whole facts form, draft, review, calendar, confirmed publication, result and next cycle | Partial |
| 5 | New user — automation | Safe preview; registration continuity; web and Mini App share the same action; configuration, preflight review, approval boundary and transition to run are exercised | The actual supervised run, result review and next-cycle transition are not exercised end to end | Partial |
| 6 | Existing owner — reviews | An unanswered review opens with a prepared draft, copy action and explicit manual-publication boundary; no runtime errors in the tested page | Confirmed provider publication is intentionally not executed on staging | Pass for safe/manual scope |
| 7 | Existing owner — finance | File preview, explicit import, and duplicate retry are exercised; second import produces two dedupe skips instead of duplicate accounting | Error-row correction and mixed valid/invalid file UX are covered indirectly, not by this staging browser suite | Pass for primary path |
| 8 | Network manager | Network aggregate, location switch, state restoration and 403 responses for foreign business/network scopes are exercised | No remaining primary-path gap found | Pass |
| 9 | Web ↔ Mini App | Shared action status, web-to-Mini-App continuity, idempotent replay, stale-version rejection and offline retry are exercised | The strongest proof uses the automation flow; every vertical is not independently repeated across both surfaces | Pass for shared contract |
| 10 | Admin creates journey | Selected flow, client preview, public privacy, link creation, revoke and HTTP 410 after revoke passed; a new empty PostgreSQL database migrates to `20260830_003` with the required partnership columns and indexes, and request paths no longer execute DDL | Expiry and single-claim conflicts are proven by backend tests, not a current full browser E2E rerun | Partial; clean-schema defect fixed |

## Security gates

| Gate | Current evidence | Status |
|---|---|---|
| Browser auth and CSRF | Browser session uses `HttpOnly`, `Secure`, `SameSite=Lax`; unsafe cookie-authenticated requests require a matching CSRF header; browser E2E confirms no bearer token in `localStorage` | Pass |
| Tenant isolation | Network browser test and backend authorization tests reject foreign business and network scopes | Pass for tested scopes |
| Public journey links | Expiry, revocation, tenant reservation, single claim, allowlisted guest events and removal of full messages/contacts are covered by focused tests | Pass |
| Error redaction | Auth, public auth, progress, content voice, integrations and sales-room failures return safe errors; provider/SQL details stay server-side | Pass for audited routes |
| SSRF | Media downloads reject loopback, private/link-local destinations and unsafe redirects while retaining the configured proxy route. Action Orchestrator callbacks reject forbidden destinations when accepted and enqueued, revalidate before delivery, pin delivery to the validated public IP while preserving the original TLS hostname, do not follow redirects and treat every 3xx as a failed attempt | Pass for media and callback paths; proxy-only callback deployments need an operational compatibility check |
| Upload content validation | Media and public sales-room uploads verify signatures and OpenXML structure instead of trusting extension/MIME | Pass |
| Approval boundaries | Existing audits and focused tests keep sends, publishing, payments and automation execution behind review/preflight/manual confirmation | Pass for audited actions |
| Dependency audit | Python audit reports no known vulnerabilities; npm production and full audits report zero vulnerabilities | Pass at current lockfiles |
| Accessibility | Axe on all five public journey previews passes with zero serious/critical findings at desktop, laptop and mobile sizes (15/15 focused checks) | Pass for public preview; authenticated workspaces remain pending |
| Secrets | Redacted Gitleaks tree scan reports 28 candidates. Confirmed live-looking credentials are concentrated in ignored `.env` and `.env.bak.2026-03-21-173649`: Stripe, Telegram, GCP and generic provider tokens. The completed history scan reports 620 candidates: mostly generic-key patterns in historical debug/tracking payloads, plus 2 JWT findings for `.env` in 2 commits. Documentation/test findings require triage. Values are not copied into this report | Failed until provider rotation, local-backup cleanup approval and history remediation decision |
| Static analysis | A new Semgrep auto-config run did not start because auto config and disabled metrics are incompatible; earlier results are not a durable current gate | Not proven |
| Source/config scan | Native Trivy secret/misconfiguration scan completed: 0 vulnerability objects in the selected no-DB profile, 4 secret findings in ignored environment files and 5 Dockerfile misconfigurations | Failed |
| Container vulnerabilities | Docker is unavailable, so the built application/Telegram images have not been scanned. Trivy's vulnerability DB was downloaded successfully but removed again when free disk fell to 1.1 GB | Not proven |
| ZAP baseline | The attempted rerun did not complete because Docker stopped | Not proven in current run |
| Journey monitoring | Health check covers orphan/stale/blocked actions, missing links/entities and notification dedupe failures; staging result was clean | Pass |

## Reproduced defects and red-to-green evidence

1. The partnership type mismatch was reproduced in three related endpoints:
   PostgreSQL compared `parsequeue.business_id` (`text`) with
   `prospectingleads.parse_business_id` (`uuid`) and the response exposed SQL
   details. Queries now compare normalized text identifiers and audited routes
   return the standard safe internal error. The same PostgreSQL browser
   regression is green in all three viewports.
2. Public journey contrast was red in all five flows: the primary action was
   2.64:1 and the approval note 4.43:1. Both use accessible design-system
   colors now; the exact Axe regression is green for five flows across three
   viewports (15/15).
3. The missing clean-schema partnership columns and request-time DDL were
   reproduced by seven focused failures. Migration `20260830_003` adds the
   columns and indexes, while the compatibility helper no longer mutates the
   schema or commits during a request. The targeted regression is green, an
   existing native staging database upgrades successfully, and a separate
   empty PostgreSQL probe database migrated through the full Alembic chain
   with the expected UUID column and three indexes.
4. Both application Dockerfiles run as root. The main and Telegram
   Dockerfiles have no image-level `HEALTHCHECK`, and `Dockerfile.telegram`
   inherits an untagged local image name. Trivy classifies the root findings
   as high severity; production compose/runtime compensating controls have not
   yet been proven.
5. Ignored local environment files contain multiple live-looking provider
   credentials, including a dated backup copy. Rotation is an external action;
   removing the backup is destructive and therefore requires explicit scope.
6. The callback SSRF candidate was reproduced by five forbidden destinations
   being accepted into the outbox. Callback URLs are now restricted to public
   HTTP(S) destinations at request and enqueue time. Dispatch resolves and
   validates again, connects to a pinned public IP, keeps the original TLS
   hostname and Host header, disables redirects and bounds response capture.
   The focused callback/media/schema/error profile is green (15/15), and the
   broader security/journey profile is green (117/117). No internal endpoint
   was contacted during reproduction.

## Required work before rollout

1. Add the missing full-cycle browser coverage for maps, influencers, content,
   partnerships and the automation result/next-cycle stage.
2. Repeat Axe on authenticated workspaces and verify the pinned callback route
   in an environment that uses the production outbound-network policy.
3. Restore Docker without deleting project or user data so Semgrep, Gitleaks,
   Trivy and ZAP can be repeated; the native fallback remains available for
   application E2E meanwhile.
4. Repeat Semgrep with explicit local rules,
   Gitleaks with redaction, Trivy and ZAP baseline.
5. Rotate the exposed Wordstat credentials externally. Decide separately
   whether Git-history rewriting is acceptable; do not rewrite history as part
   of an ordinary application deployment.
6. Run the full 10-scenario suite, journey health check, backend security
   profile and frontend build/typecheck after all fixes.
7. Prepare a flag-by-flag rollout package. Do not deploy to production without
   a separate explicit authorization and a production database backup where a
   migration is involved.
