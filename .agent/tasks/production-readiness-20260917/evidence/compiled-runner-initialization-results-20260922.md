# Compiled runner initialization — local FIX_PROVEN

Finding `RUNNER-INIT-01`, P2 reliability/diagnostics. A bind failure in
`HTTPServer.__init__` calls the overridden `server_close` before `pool` exists.
The resulting `AttributeError` masks the original socket error. This does not
cause the bind failure or prove a production outage, but makes startup failures
harder to diagnose. It affects failed initialization only; confidence is high
from an identical-test red/green comparison. Operational likelihood is unmeasured.

The minimal fix checks whether the pool exists after calling the parent close.
Normal initialized shutdown still calls `pool.shutdown(wait=True)`. No exception
is swallowed and no network, policy, API or database contract changes. Risk and
effort are low; rollback is the single server-close guard. Required before claiming
the runner's startup-error path verified, not an authorization to deploy it.

## Verification

- `red-green-v2.json`: same two test functions against HEAD at execution
  (`c1dd64ee`, runner digest `ba59b653...b4471`) and the patched worktree.
  Baseline bind-denial case raises `AttributeError`; baseline normal shutdown
  passes. Patched cases both pass. Capture 222.180 ms, exit 0. The executed
  script is archived byte-for-byte; its historical `HEAD` lookup must not be
  rerun after the fix commit and mistaken for the old baseline.
- `adjacent-v2.json`: 11 tests pass in 0.36 s (wrapper 633.992 ms), comprising
  the two new cases, four typed HTTP-error cases and five pure artifact/runtime
  admission cases. OS sandbox denies all network and unowned writes. Explicit
  `TMPDIR=/private/tmp/compiled-runner-initialization-evidence`, plugin autoload,
  dotenv and bytecode disabled, pytest cache disabled. No DB/provider calls.
- `adjacent-v1.json`: retained failed attempt before any tests, 225.445 ms;
  missing owned TMPDIR prevented pytest creating capture files. V2 changes only
  the environment, not assertions. Its stderr is explicitly capture-truncated.
- `focused-pytest.json`: historical two-pass run before the test close-spy was
  corrected to call the original parent close. It is not current-test evidence.
- Focused Ruff F821/F822/F823 and diff checks pass. Independent reviewer inspected
  the minimal fix, identical red/green assertions and hashes, then independently
  ran both current regression tests successfully. Adjacent package review follows.

The bind test creates an unbound socket and mocks `server_bind` before any bind;
the spy calls the original parent close. These tests do not prove a real HTTP
listen/request flow. The full frozen backend baseline remains failed, and the
image, current-source aggregate and original whole-audit gates remain open.

Seven SHA256SUMS entries bind five captures/script files plus current server/test.
No foreign worktree files are included and no image was rebuilt or deployed.
