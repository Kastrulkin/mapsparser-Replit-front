# Google Business Profile For LocalOS

Status: `beta / Google Basic API Access approved`.

Last verified: 4 September 2026. Google approved the allowlist request for
project `649313441761` on 2026-09-03 and granted the default `300 QPM` quota.

## Current Decision

LocalOS has two Google Cloud/OAuth contexts in history:

1. the previous production OAuth client under `totemic-union-440908-s8`;
2. the current production OAuth client under the approved `localos-gbp` project.

The production server switched to the approved `localos-gbp` OAuth client on
2026-09-04. Keep the previous `.env` backup available until a real business
OAuth connection and read-only sync pass.

## Production Source Of Truth

Production LocalOS currently uses this OAuth client:

`649313441761-bht1r6b8r1qt8viqa3k06kcnlgkj5ltq.apps.googleusercontent.com`

This is the account binding that matters for runtime checks. In Google Cloud
Console the client is visible under project `localos-gbp`, while the project
selector displays `LocalOS GBP`.

## Previous Google Cloud Project

- Project ID: `totemic-union-440908-s8`
- Google Cloud project selector / project number shown in Console: `510204060`
- OAuth app name: `LocalOS`
- User support email: `demyanovap@gmail.com`
- OAuth client type: Web application
- OAuth client name: `LocalOS Web OAuth Client`
- OAuth client ID: `304042072643-cpvhm8toat1aag3lc2enudfclfouhhod.apps.googleusercontent.com`
- Authorized JavaScript origin: `https://localos.pro`
- Authorized redirect URI: `https://localos.pro/api/google/oauth/callback`

Do not commit the OAuth client secret. Store it only in production environment variables.

## New GBP Allowlist Project

The repeat application uses a separate project for Google Business Profile API
approval. The active request uses the verified LocalOS Business Profile as the
applicant evidence profile and submits the company website exactly as shown on
the public profile: `https://localos.pro/`.

- Google Cloud project name: `LocalOS GBP`
- Project ID: `localos-gbp`
- Project number: `649313441761`
- OAuth app name: `LocalOS`
- OAuth client name: `LocalOS Production`
- OAuth client ID: `649313441761-bht1r6b8r1qt8viqa3k06kcnlgkj5ltq.apps.googleusercontent.com`
- User support email: `demyanovap@gmail.com`
- Agency/contact account: `info@localos.pro`
- Authorized domain: `localos.pro`
- Authorized redirect URI: `https://localos.pro/api/google/oauth/callback`

The OAuth client secret is intentionally not documented or committed.

### Agency Organization And First Managed Profile

- Applicant GBP profile: `LocalOS`
- Applicant profile type: service-area business
- Applicant profile status: `Verified`
- Applicant profile website: `https://localos.pro/`
- Applicant listing/fid observed in Google Search: `1691055692617577882`
- GBP organization: `LocalOS`
- Organization ID: `110155982680425683163`
- Location group: `Клиенты LocalOS`
- Location group ID: `113125848042085196875`
- Managed client: `Веселая расческа`
- Address: `Проспект Энгельса, 154, ТРК "Гранд Каньон", Санкт-Петербург`
- Store code: `13577141863377705865`
- Status in the agency group: `Verified`
- LocalOS access level: manager
- Primary ownership: unchanged

The LocalOS profile is the applicant evidence profile for API access. Managed
client profiles remain proof of the agency/SaaS use case, but they should not be
selected as the applicant profile when the company website field is
`https://localos.pro/`.

## Required Environment Variables

Set these on the server/app runtime:

```bash
GOOGLE_CLIENT_ID=304042072643-cpvhm8toat1aag3lc2enudfclfouhhod.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
GOOGLE_REDIRECT_URI=https://localos.pro/api/google/oauth/callback
GOOGLE_CLOUD_PROJECT_ID=localos-gbp
FRONTEND_URL=https://localos.pro
```

## Required Google Access

Google Business Profile APIs require Basic API Access approval before production API calls work. Google documents the approval signal as quota:

- `0 QPM`: project is not approved yet;
- `300 QPM`: project is approved for the relevant GBP APIs.

Submit the access request from Google Business Profile Help:

`https://support.google.com/business/workflow/16726127?hl=en`

The approved repeat application was submitted with:

- request type: `Application For Basic API Access`;
- signed-in account: `Demyanovap@gmail.com`;
- Google Cloud project number: `649313441761`;
- company website: `https://localos.pro/`;
- verified applicant profile: `LocalOS`;
- use case: authorized owners and agencies connect their own Business Profiles
  to LocalOS to manage business information, services, approved posts, reviews,
  and performance data. External writes remain subject to explicit approval.
- submitted on 2026-09-01;
- approved on 2026-09-03;
- approval email support case ID: `1-0494000040762`;
- Google Cloud project number approved: `649313441761`;
- granted quota: `300 QPM`.

### Google Policy Reminder

LocalOS must describe this as an integration with Google Business Profile APIs.
Do not make public statements that imply LocalOS is a Google partner, is
sponsored by Google, or is endorsed by Google unless Google grants separate
written approval.

Earlier response in the same support thread:

- submitted on 2026-08-14;
- Google support case ID: `1-0494000040762`;
- selected evidence profile: `LocalOS`;
- profile website shown publicly: `https://localos.pro/`;
- company website submitted in the form: `https://localos.pro`;
- result on 2026-08-27: Google reported a URL mismatch because the application
  website omitted the trailing slash shown on the public Business Profile URL;
- final result on 2026-09-03: Google approved the project after the corrected
  application used `https://localos.pro/` exactly.

Rejected application superseded by the LocalOS-profile request:

- submitted on 2026-07-18;
- Google support case ID recorded in the setup work: `7-6688000041542`;
- user-facing help workflow confirmation ID: `0-1749000041409`;
- selected evidence profile: `Веселая расческа`, Проспект Энгельса, 154;
- company website: `https://localos.pro`;
- result on 2026-08-06: rejected by Google's internal quality checks because
  the selected listing ID was associated with a different website.

Historical application (not the current allowlist request):

- submitted on 2026-06-17;
- project `totemic-union-440908-s8`;
- case `7-7493000041066`;
- result: rejected by Google's internal quality checks.

## LocalOS Flow

1. User opens external integrations.
2. User clicks `Подключить Google`.
3. LocalOS redirects to Google OAuth with `business.manage` and Google Sheets scopes.
4. Google callback stores encrypted credentials in `externalbusinessaccounts`.
5. User loads accessible GBP locations.
6. User selects the location that maps to the LocalOS business.
7. User runs sync to import reviews and performance data.
8. LocalOS creates drafts/previews for external writes.
9. Publishing review replies or posts requires explicit UI approval. Direct publish endpoints reject requests without `approved: true`.

## Verification

Backend syntax:

```bash
python3 -m py_compile src/google_business_api.py src/google_business_sync_worker.py src/api/google_business_api.py
```

Frontend build:

```bash
cd frontend
npm run build
```

Production deploy reminder:

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 15m app
docker compose logs --since 15m worker
curl -I http://localhost:8000
```

## Current Limitations

- The new `localos-gbp` client is installed in production, but one real business
  OAuth connection and read-only sync still need to pass before external writes
  are treated as live.
- GBP API services were confirmed enabled in Google Cloud Console on
  2026-09-04 for project `649313441761`: My Business Account Management API,
  My Business Business Information API, Google My Business API, and Business
  Profile Performance API.
- Service and price-list writes depend on GBP category support. LocalOS must keep preview and manual approval before any external write.

## Post-Approval Checklist

1. Done 2026-09-04: confirm that the relevant GBP API quota for project
   `localos-gbp` is `300 QPM`.
2. Done 2026-09-04: back up the current production environment values.
3. Done 2026-09-04: set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to the
   new OAuth client; keep
   `GOOGLE_REDIRECT_URI=https://localos.pro/api/google/oauth/callback`.
4. Done 2026-09-04: recreate `app` and `worker` with the new environment.
5. Done 2026-09-04: server-side OAuth URL smoke confirms the new client ID,
   `business.manage` scope, and production redirect URI.
6. Complete OAuth for one LocalOS business and verify account/location listing.
7. Bind the LocalOS business to the correct GBP location.
8. Run a read-only sync and verify reviews/profile data.
9. Prepare one post, require explicit approval, publish it, and store the Google
   provider result/ID.
10. Keep the previous OAuth credentials available for rollback until the live
   proof succeeds.
