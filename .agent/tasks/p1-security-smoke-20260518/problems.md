# Problems: p1-security-smoke-20260518

### AC5: Live production secret is present and non-weak
- Status: FAIL
- Why it is not proven: live `EXTERNAL_AUTH_SECRET_KEY` is missing.
- Minimal reproduction steps: run `scripts/smoke_security_runtime.sh server`.
- Expected: secret presence check prints `EXTERNAL_AUTH_SECRET_KEY=present`.
- Actual: secret presence check prints `EXTERNAL_AUTH_SECRET_KEY=missing`.
- Affected files/config: `/opt/seo-app/.env`, external auth encryption/decryption.
- Smallest safe fix: recover the original encryption secret and set it in `/opt/seo-app/.env`, then recreate `app worker`.
- Corrective hint: there are 3 encrypted `externalbusinessaccounts` records. If the original secret is unavailable, choose a new 32+ char secret only with approval, then re-save/rotate external account auth data.
