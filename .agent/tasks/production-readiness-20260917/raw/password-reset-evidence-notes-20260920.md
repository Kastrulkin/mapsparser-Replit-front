# Password reset: causal evidence and execution correction

Parent: `cf36cbb0`. Finding: SEC-AUTH-RESET-02. Scope: local handler plus
transactional fake, actual Flask compatibility route, real DBConnectionWrapper,
password hashing and session verification. No native database or provider proof.

## Invalid preliminary worker evidence

The worker initially ran a shared-venv pytest command with `env -i`, PATH/HOME,
TMPDIR and PYTHONPATH=src, without the required guard or tmux/capture. `main`
can load the repository `.env` during import before monkeypatches are installed.
The worker also reported subsequent focused/adjacent runs in that profile.
Root stopped that worker and took exclusive ownership of files and execution.
No durable raw capture exists for those reported runs. Their side effects are
INCONCLUSIVE; do not claim that `.env`, DB or providers were untouched by them.
No evidence establishes a production mutation either. No compensating write,
credential change or cleanup was attempted.

The initial plain-dictionary fixture was also incorrect: `main` uses
DBConnectionWrapper/HybridRow, which supports positional indexing, whereas
auth_system uses raw RealDictCursor. The SELECT projection must be id, token,
expiry in that order, not the whole user dictionary. The reported KeyError is
not a production-shaped causal result and is excluded.

## Authoritative guarded root runs

The support script pins cwd, PYTHONPATH, main origin, trusted inherited guard
SHA and historical handler SHA; rejects Git/database overrides; disables dotenv;
denies actual psycopg2 connections, socket operations and arbitrary child
processes. The only allowed subprocess reads the pinned historical handler.
The launcher uses env -i and the private ARM64 venv in named tmux sessions.
This is a trusted-bootstrap process-local guard, not an OS sandbox.

Retained harness failures:

- `password-reset-guarded-baseline`: Flask-SQLAlchemy required a synthetic URI
  even without connecting. Import failed before pytest, 2639.503ms, exit1.
- `password-reset-guarded-baseline2`: 6 failed/1 passed but guard exit79, one
  denied socket operation; not the authoritative final RED.
- `password-reset-guard-diagnostic`: 7 passed but exit79, with stack proving
  urllib3's import-only `_has_ipv6` local bind probe. The guard denied it.
  The final fixture sets socket.has_ipv6=False to avoid that irrelevant probe;
  no network exception was granted, no counter reset or assertion weakened.

Final script SHA: `39cd4689b69aeceb7d55def0317f5cb5d4623d0828f020d31d790a2696dbd848`.

| Capture | Result | Duration |
| --- | --- | --- |
| password-reset-guarded-red | 6 failed / 1 passed, exit1 | pytest0.44s; capture2765.219ms |
| password-reset-guarded-green | 7 passed, exit0 | pytest0.43s; capture2386.050ms |
| password-reset-guarded-adjacent | 16 passed, exit0 | pytest0.53s; capture2586.098ms |

All three final runs have zero recorded denied network/DB/dotenv/child/inherited
attempts, no timeout, no truncation and empty stderr. Adjacent includes the seven
reset cases plus three auth-security and six browser-session cases; counts are
overlapping, not 23 distinct tests. Quality capture includes syntax, narrowly
scoped Ruff, diff check and nine source/test/guard hashes. `main.py` is an existing
foreign dirty file: its tested hash is recorded, but it is not included in this
commit. The suite is not an exact clean-commit whole-app certification.

## What the RED does and does not prove

The pinned cf36cbb0 handler receives a real-wrapper-shaped native datetime and
raises TypeError at fromisoformat, returning500 for a valid reset. The TIMESTAMP
column is declared in migration20260224_add_users_reset_columns. Invalid-token
early return also leaves the fake connection unclosed, and an array JSON body
returns500. The rollback test's baseline failure happens at date parsing before
the injected session-delete failure; it is not a distinct baseline atomicity
reproduction. Six failed assertions do not mean six independent defects.

The fix accepts native and ISO timestamps, validates input, closes connections
on every route path, and atomically changes the hash, consumes the token and
revokes existing sessions for only that user. FOR UPDATE provides the intended
serialization mechanism, but fake tests do not prove PostgreSQL lock behavior.
Session revocation is deliberate account-recovery hardening consistent with
OWASP Forgot Password guidance, not a proven successful native-baseline exploit.
The normal set_password/change_password helpers remain unchanged. Concurrent
logins, rate-limiter parity of the stripped historical decorator, native rollback,
live email/reset, production and complete backend aggregate remain unverified.

Reference: https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html
