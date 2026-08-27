# Evidence Bundle: lead-journey-v2-20260827

## Summary

- Overall status: PASS
- Last updated: 2026-08-27
- Runtime mutation: local code and deterministic local browser fixtures only;
  production DB and feature flags were not changed.

## Acceptance criteria evidence

### AC1 — Four canonical flows: PASS

- Migration `20260827_002` extends both constraints without editing the applied
  journey migration and adds the flow/status index.
- Service/API types, feature flags and frontend mapping support influencer,
  partnership, maps and content; upgrade remains action-only.
- Migration, flow and vertical kill-switch tests passed.

### AC2 — Deterministic creation/public experience: PASS

- New journey creation requires `selected_flow` and rejects an entity outside
  the safe preview.
- Public serialization strips contact/private keys, truncates copy, and accepts
  only safe public URLs.
- Browser pass opened four tokenized links directly on their selected path with
  one primary CTA and secondary areas disabled.

### AC3 — Auth continuity: PASS

- Shared resolver retains the token until a successful claim and maps only
  allowlisted screen keys.
- Email verification can claim a pre-bound pending journey without putting the
  public token in the verification link.
- Local browser login + claim opened the exact action route; reserved-journey,
  tenant mismatch, expiry/revocation, idempotency and stale-version tests passed.

### AC4 — Content vertical: PASS

- Content actions project onto existing content plans/items and update domain
  state before creating the next action in the same transaction.
- Draft, schedule, publication, result and next-cycle transitions are validated.
- External publication remains a manual/provider-confirmed record and existing
  approval boundary.

### AC5 — Admin builder: PASS

- Superadmin-only client -> path -> example -> public/auth/paid preview -> link
  wizard is available at `/dashboard/bazich/journeys`.
- It lists lifecycle/latest action/event, prepares the message, copies/opens the
  link and revokes without SQL.
- Non-superadmin test passed; positive browser pass completed the content route.

### AC6 — Growth-path IA: PASS

- `/dashboard/growth-paths` renders Maps, Content, Influencers and Partnerships,
  sorts the active action first, and shows one CTA per path.
- Sidebar is flag-gated as Today / Growth paths / Results / More; legacy routes
  remain registered.
- Browser QA found and fixed a doubled `/api/api` path; regression coverage was
  added for the correct client endpoint.

### AC7 — Block-level access: PASS

- Shared `AccessPreview`/`AccessBoundary` implements all six access states with a
  readable reason and CTA.
- Growth paths use backend-produced access contracts. The influencer workspace
  keeps the exact journey action visible and locks only the expanded workspace.
- Unconverted paid screens retain the old route gate; frontend styling is not
  treated as authorization.

### AC8 — Navigation/cross-area exploration: PASS

- Web and Mini App top-level order matches the new IA under independent flags.
- Mini App keeps old operational areas under More and maps review deep links to
  Growth paths while retaining the concrete review screen.
- Scope-integrity, stale-response, review and Operator approval tests pass.

### AC9 — Web/Mini parity/telemetry: PASS

- Shared action identity/version/status/allowed-command contract is used on web
  and Mini App, with `surface` and idempotency key forwarded to backend.
- Funnel dimensions include verification, claim, workspace, content, redirect
  failures, stale/orphan and subscription events.
- Diagnostics expose flags, flow/status counts, orphan/stale/blocked actions,
  notification failures and action/domain mismatch.

### AC10 — Quality/security/rollout readiness: PASS

- Backend: 48 targeted tests passed.
- Frontend: 44 targeted tests passed across 9 files.
- Production frontend build, Python compile and targeted diff check passed.
- Browser acceptance covered four deterministic public flows, post-auth exact
  destination, admin builder, Growth paths, block access and Mini App.
- Rollout runbook requires backup, staged flags, smoke checks and non-destructive
  rollback. Production execution remains pending explicit approval.

## Commands run

- `arch -arm64 python3 -m pytest -vv ...` — 48 passed.
- `npm test -- --run ...` — 44 passed in 9 files.
- `npm run build` — passed.
- `arch -arm64 python3 -m py_compile ...` — passed.
- `git diff --check -- <journey scope>` — clean.
- `scripts/proof_loop.sh validate lead-journey-v2-20260827` — valid.

## Raw artifacts

- `raw/backend-tests-verbose.txt`
- `raw/frontend-tests.txt`
- `raw/frontend-build.txt`
- `raw/browser-smoke.md`
- `raw/screenshot-public-content.png`
- `raw/screenshot-admin-builder.jpg`
- `raw/screenshot-growth-paths-viewport.jpg`
- `raw/screenshot-influencer-block-access.jpg`
- `raw/screenshot-mini-app-viewport.jpg`

## Known operational follow-up

- Production migration/flags were not executed because they require explicit
  approval and a verified PostgreSQL backup.
- The first production pilot should use the internal Варвара business and keep
  notifications/upsell disabled until real cycles are observed.
