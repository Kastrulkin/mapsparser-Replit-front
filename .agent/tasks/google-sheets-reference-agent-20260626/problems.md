# Problems: google-sheets-reference-agent-20260626

## External Blocker: Google OAuth reconnect required

- Status: BLOCKED_OUTSIDE_CODE
- Why it is not fully proven: production can only perform live Google Sheets read after the user reconnects Google and grants the new Sheets scope.
- Minimal reproduction steps: run `PYTHONPATH=/app/src BUSINESS_ID=<business_id> python scripts/smoke_google_sheets_reference_agent.py` before reconnecting Google.
- Expected: smoke returns `success: true`, `capability_read: true`, `result_status: read_completed`.
- Actual before reconnect: smoke returns a blocked state such as `google_sheets_integration_has_no_auth_ref` or `GOOGLE_SHEETS_PROVIDER_NOT_READY`.
- Affected files: `src/google_business_auth.py`, `src/api/agent_blueprints_api.py`, `scripts/smoke_google_sheets_reference_agent.py`.
- Smallest safe fix: reconnect Google in settings after deploy; OAuth callback now binds existing active Google Sheets integrations automatically.
- Corrective hint: do not manually edit credentials in DB; use OAuth so encrypted credentials and scopes are correct.
