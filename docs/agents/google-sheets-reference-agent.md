# Google Sheets Reference Agent

Status: `beta`

This is the reference Compiled AI scenario for proving the custom-agent runtime:

```text
Google Sheets
-> OAuth binding
-> Agent integration
-> Preflight
-> Compiled blueprint
-> Runner
-> Approval stop
-> Artifact / run evidence
```

The scenario intentionally does not require Telegram or WhatsApp delivery. The
runtime must be able to read rows, prepare a result, stop before external action,
and leave observable evidence in the run journal.

## Required Runtime Contract

- Google OAuth credentials must include
  `https://www.googleapis.com/auth/spreadsheets`.
- `agent_integrations.provider = 'google_sheets'` must have `auth_ref` pointing
  to an active `externalbusinessaccounts` row.
- The integration config must include `spreadsheet_id` and `sheet_name`.
- `google_sheets.read_rows` may run without human approval because it is read
  only.
- Any later external send or spreadsheet write must stop at approval.

## Smoke

Run in the backend runtime:

```bash
PYTHONPATH=/app/src BUSINESS_ID=<business_id> \
  python scripts/smoke_google_sheets_reference_agent.py
```

Optional:

```bash
GOOGLE_SHEETS_INTEGRATION_ID=<integration_id>
SPREADSHEET_ID=<spreadsheet_id>
SHEET_NAME=<sheet_name>
LIMIT=5
```

PASS means the smoke reached real provider read:

- `oauth_binding: true`
- `integration: true`
- `capability_read: true`
- `result_status: read_completed`

If the smoke returns `google_sheets_integration_has_no_auth_ref`, reconnect
Google and then save/select the Google Sheets integration again so LocalOS binds
the account to the agent runtime.
