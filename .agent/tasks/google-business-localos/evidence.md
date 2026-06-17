# Evidence Bundle: google-business-localos

## Summary
- Overall status: PARTIAL_PASS
- Last updated: 2026-06-17T08:45:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PARTIAL_PASS
- Proof:
  - Google Auth Platform created for project `totemic-union-440908-s8` / project number `510204060`.
  - OAuth app name set to `LocalOS`.
  - Web OAuth client `LocalOS Web OAuth Client` created with origin `https://localos.pro` and redirect `https://localos.pro/api/google/oauth/callback`.
  - GBP Basic API Access request submitted. Google support case ID: `7-7493000041066`.
- Gaps:
  - Waiting for Google review. Google stated review time: approximately 7-10 business days.

### AC2
- Status: PASS
- Proof:
  - `src/api/google_business_api.py` now stores callback credentials in the runtime `auth_data_encrypted` column, with fallback for older `auth_data`.
  - `src/google_business_sync_worker.py` reads either `auth_data_encrypted` or legacy `auth_data`.
- Gaps:
  - Runtime OAuth callback needs server env values before live verification.

### AC3
- Status: PASS
- Proof:
  - Added `GET /api/business/<business_id>/google/locations`.
  - Added `POST /api/business/<business_id>/google/bind-location`.
  - `GoogleBusinessAPI` now lists accessible locations via Business Information API when available.
- Gaps:
  - Live call requires approved/enabled GBP APIs.

### AC4
- Status: PASS
- Proof:
  - Added `POST /api/business/<business_id>/google/sync`.
  - Google review parser now handles top-level GBP review payload fields and paginated review lists.
- Gaps:
  - Live sync requires OAuth env and Google API access.

### AC5
- Status: PASS
- Proof:
  - Review reply and post publish endpoints return `409 manual_approval_required` unless payload includes `approved: true`.
  - Product docs state Google writes require manual approval.
- Gaps:
  - Existing approval queues can be integrated more deeply in a later phase for one-click approval execution.

### AC6
- Status: PASS
- Proof:
  - `frontend/src/components/ExternalIntegrations.tsx` now exposes a Google Business Profile task flow: connect, find locations, select location, sync.
- Gaps:
  - Browser visual QA against local app is still pending.

### AC7
- Status: PASS
- Proof:
  - Added `docs/GOOGLE_BUSINESS_PROFILE_LOCALOS_SETUP.md`.
  - Updated `docs/integrations.md`.
- Gaps:
  - OAuth client secret intentionally not recorded.

## Commands run
- `python3 -m py_compile src/google_business_api.py src/google_business_sync_worker.py src/api/google_business_api.py` -> PASS
- `cd frontend && npm run build` -> PASS
- Browser: Google Auth Platform setup -> PASS
- Browser: OAuth web client creation -> PASS
- Browser: GBP Basic API Access form -> submitted after user completed reCAPTCHA; case `7-7493000041066`
- Browser: `http://127.0.0.1:3000/` loaded, no local `127.0.0.1` console errors -> PASS

## Raw artifacts
- .agent/tasks/google-business-localos/raw/build.txt
- .agent/tasks/google-business-localos/raw/test-unit.txt
- .agent/tasks/google-business-localos/raw/test-integration.txt
- .agent/tasks/google-business-localos/raw/lint.txt
- .agent/tasks/google-business-localos/raw/screenshot-1.png

## Known gaps
- Google must approve GBP Basic API Access case `7-7493000041066`.
- Production server env must be updated with `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`, `FRONTEND_URL`.
- Live OAuth/sync verification requires deployed env and Google API access approval.
