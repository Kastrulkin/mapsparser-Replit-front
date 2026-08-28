# Google Business Profile For LocalOS

Status: `beta / Google Basic API Access rejected / ready to resubmit`.

Last verified: 27 August 2026. Google rejected the 14 August request because
the website URL in the application did not exactly match the URL publicly shown
on the LocalOS Business Profile. The public profile URL is recorded as
`https://localos.pro/`, while the application used `https://localos.pro`.

## Current Decision

LocalOS has two Google Cloud/OAuth contexts during the review period:

1. the current production OAuth client, which must remain unchanged while the
   new application is under review;
2. the new `localos-gbp` project submitted for Google Business Profile Basic
   API Access.

Do not replace production credentials with the new client until Google approves
the new project and the post-approval smoke checklist below passes.

## Production Source Of Truth

Production LocalOS currently uses this OAuth client:

`304042072643-cpvhm8toat1aag3lc2enudfclfouhhod.apps.googleusercontent.com`

This is the account binding that matters for runtime checks. Do not confuse it
with older project-number notes. In Google Cloud Console the client is visible
under project `totemic-union-440908-s8`, while the project selector displays
`510204060`. Runtime errors and OAuth credentials may also include the numeric
client prefix `304042072643`; treat that prefix as the active LocalOS OAuth
client identifier, not as a separate LocalOS integration.

## Google Cloud Project

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
approval. The next access request must use the verified LocalOS Business Profile
as the applicant evidence profile and must submit the company website exactly as
shown on the public profile: `https://localos.pro/`.

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
FRONTEND_URL=https://localos.pro
```

## Required Google Access

Google Business Profile APIs require Basic API Access approval before production API calls work. Google documents the approval signal as quota:

- `0 QPM`: project is not approved yet;
- `300 QPM`: project is approved for the relevant GBP APIs.

Submit the access request from Google Business Profile Help:

`https://support.google.com/business/workflow/16726127?hl=en`

The next repeat application should be submitted with:

- request type: `Application For Basic API Access`;
- signed-in account: `Demyanovap@gmail.com`;
- Google Cloud project number: `649313441761`;
- company website: `https://localos.pro/`;
- verified applicant profile: `LocalOS`;
- use case: authorized owners and agencies connect their own Business Profiles
  to LocalOS to manage business information, services, approved posts, reviews,
  and performance data. External writes remain subject to explicit approval.

Rejected application superseded by the next request:

- submitted on 2026-08-14;
- Google support case ID: `1-0494000040762`;
- selected evidence profile: `LocalOS`;
- profile website shown publicly: `https://localos.pro/`;
- company website submitted in the form: `https://localos.pro`;
- result on 2026-08-27: rejected because the application website URL did not
  exactly match the Business Profile website URL.

Google-stated review time for a new request is typically approximately 7-10
business days.

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

- The new `localos-gbp` client is not installed in production while review is pending.
- GBP API calls for the new project may fail until Google approves Basic API Access.
- Service and price-list writes depend on GBP category support. LocalOS must keep preview and manual approval before any external write.

## Post-Approval Checklist

1. Confirm that the relevant GBP API quota for project `localos-gbp` is no
   longer `0 QPM` and matches the approved allowance.
2. Back up the current production environment values.
3. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to the new OAuth client;
   keep `GOOGLE_REDIRECT_URI=https://localos.pro/api/google/oauth/callback`.
4. Restart only `app` and `worker`.
5. Complete OAuth for one LocalOS business and verify account/location listing.
6. Bind the LocalOS business to the correct GBP location.
7. Run a read-only sync and verify reviews/profile data.
8. Prepare one post, require explicit approval, publish it, and store the Google
   provider result/ID.
9. Keep the previous OAuth credentials available for rollback until the live
   proof succeeds.
