# Evidence Bundle: auth-registration-production-20260511

## Summary
- Overall status: PASS
- Last updated: 2026-05-11

## Acceptance criteria evidence

### AC1: Registration requires personal-data consent
- Status: PASS
- Proof:
  - Backend `/api/auth/register` and `/api/auth/register-with-business` reject requests without `personal_data_consent`.
  - Frontend registration form has an explicit required checkbox with link to `/policy`.
  - Registration button is disabled until consent is checked.

### AC2: New users must verify email before login/session
- Status: PASS
- Proof:
  - `create_user` stores `is_verified=False` and a `verification_token`.
  - Registration endpoints no longer create a session immediately.
  - `authenticate_user` returns `EMAIL_NOT_VERIFIED` for unverified users.
  - `/api/auth/verify-email` verifies the token, marks the user verified, clears the token, and only then creates a session.

### AC3: Password setup is token-protected
- Status: PASS
- Proof:
  - `/api/auth/set-password` now requires a setup token matching `users.verification_token`.
  - Password setup also records personal-data consent.
  - Reset password remains on `/api/auth/confirm-reset`, separated from setup flow.

### AC4: Verification UX exists
- Status: PASS
- Proof:
  - Added `/verify-email` frontend page.
  - Added resend verification button after registration.
  - Added `/api/auth/resend-verification`.

### AC5: Checks pass
- Status: PASS
- Proof:
  - `python3 -m py_compile src/auth_system.py src/main.py src/messengers_api.py src/core/email_delivery.py`
  - `python3 -m pytest -q tests/test_auth_email_case_insensitive.py`
  - `npm --prefix frontend run build`

## Commands run
- `python3 -m py_compile src/auth_system.py src/main.py src/messengers_api.py src/core/email_delivery.py`
- `python3 -m pytest -q tests/test_auth_email_case_insensitive.py`
- `npm --prefix frontend run build`
- `scripts/proof_loop.sh validate auth-registration-production-20260511`

## Raw artifacts
- .agent/tasks/auth-registration-production-20260511/raw/build.txt
- .agent/tasks/auth-registration-production-20260511/raw/test-unit.txt
- .agent/tasks/auth-registration-production-20260511/raw/test-integration.txt
- .agent/tasks/auth-registration-production-20260511/raw/lint.txt
- .agent/tasks/auth-registration-production-20260511/raw/screenshot-1.png

## Known gaps
- Production migration/deploy was not run in this step.
- Existing users are not forced to re-consent; migration preserves existing access and only changes defaults for new users.
