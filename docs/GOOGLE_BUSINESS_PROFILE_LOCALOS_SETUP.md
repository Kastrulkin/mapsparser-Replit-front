# Google Business Profile For LocalOS

Status: beta / Google review pending.

## Google Cloud Project

- Project ID: `totemic-union-440908-s8`
- Project number: `510204060`
- OAuth app name: `LocalOS`
- User support email: `demyanovap@gmail.com`
- OAuth client type: Web application
- OAuth client name: `LocalOS Web OAuth Client`
- OAuth client ID: `304042072643-cpvhm8toat1aag3lc2enudfclfouhhod.apps.googleusercontent.com`
- Authorized JavaScript origin: `https://localos.pro`
- Authorized redirect URI: `https://localos.pro/api/google/oauth/callback`

Do not commit the OAuth client secret. Store it only in production environment variables.

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

Use:

- request type: `Application for Basic API Access`;
- project number: `510204060`;
- contact email: `demyanovap@gmail.com`;
- app/product: `LocalOS`;
- domain: `localos.pro`;
- use case: LocalOS helps authorized business owners and managers synchronize Google Business Profile reviews, prepare review-reply drafts, publish approved replies and posts, and manage service or price-list data only after explicit user approval.

Submitted on 2026-06-17.

- Google support case ID: `7-7493000041066`
- Google-stated review time: approximately 7-10 business days.

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

- OAuth app remains in Testing until Google verification / publishing is complete.
- GBP API calls may still fail until Google approves Basic API Access for project `510204060`.
- Service and price-list writes depend on GBP category support. LocalOS must keep preview and manual approval before any external write.
