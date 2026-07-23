# Google Sheets OAuth

Google Sheets and Google Business use independent OAuth clients and independent
`externalbusinessaccounts` rows.

## Sheets project

1. Create a dedicated Google Cloud project and enable Google Sheets API.
2. Configure the OAuth consent screen. During the Riderra pilot, add
   `riderratech@gmail.com` as a test user.
3. Create a Web application OAuth client with redirect URI:
   `https://localos.pro/api/google/sheets/oauth/callback`.
4. Configure production:

```dotenv
GOOGLE_SHEETS_CLIENT_ID=...
GOOGLE_SHEETS_CLIENT_SECRET=...
GOOGLE_SHEETS_REDIRECT_URI=https://localos.pro/api/google/sheets/oauth/callback
GOOGLE_OAUTH_STATE_SECRET=...
```

The only requested scope is
`https://www.googleapis.com/auth/spreadsheets`. Google Docs and Drive are not
part of this connection.

## Runtime contract

- `google_sheets.read_rows` reads values.
- `sheets.append_row_request` appends at most 100 values after approval.
- `google_sheets.update_cells` updates at most 100 ordinary cells after approval.
- Preview never writes.
- Update repeats the read immediately before applying and rejects changed source
  values. Existing formulas and new formula values are rejected.
- Delete, clear, sheet creation, rename and other structural operations are not
  exposed.

Google Business keeps `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and
`GOOGLE_REDIRECT_URI` and requests only `business.manage`.
