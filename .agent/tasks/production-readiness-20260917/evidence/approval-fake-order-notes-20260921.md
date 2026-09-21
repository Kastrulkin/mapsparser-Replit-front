# Approval fake ordering correction — 21 September 2026

Scope: `TEST-APPROVAL-FAKE-ORDER-01` only. This is a test-double fidelity
correction; it does not establish a production defect and did not import the
application, connect to a database, read an environment file, or make a network
request.

## Contract and cause

`AgentBlueprintRunner._approved_draft_snapshot` queries approved draft
approvals with `ORDER BY decided_at DESC, id DESC LIMIT 1`. PostgreSQL makes a
descending nullable column `NULLS FIRST` by default. `approve` writes
`decided_at = NOW()`.

The former `FakeCursor` instead returned the last inserted matching row and
left `decided_at` unchanged on its matching approval update. That could make a
multi-approval test pass while modelling a different selected row.

## Evidence

| Capture | Result |
| --- | --- |
| `approval-fake-order-red-20260921.json` | REPRODUCED: 5 of 8 deterministic tests failed against the pre-fix fake matching the recorded HEAD hash, including the explicit NULLS FIRST case. |
| `approval-fake-order-green-20260921.json` | FIX_PROVEN for this fake contract: all 8 tests pass after the minimal fake-only correction. |

Each capture launches `python3 -I` inside tmux with a socket denial guard and
import guard for application/DB/env modules. No native pytest/conftest or
runtime service was started.

## Change

`tests/agent_blueprint_fakes.py` now stably applies `id DESC`, then non-null
decision time descending, then places null decision times first; the matching
fake approval update records an aware UTC decision time. The test assertions
were not weakened.

Pre-fix fake SHA-256: `99dc3f8aae0a4d03cd6d7965ee4de937643a44bb7f1d0ae2e5bc8536181ea187`.

Current fake SHA-256: `32af1d64a54ead93518695114313862db88460e6fdb9eebc5a276b856abe9187`.

Owned paused regression-draft SHA-256: `29499b7b03f819dea771676eed02767b30c6752b1677ff6e8ac1d316e67c37c9`.

Residual limit: this proves only the in-memory test double's deterministic
ordering/update semantics. It is not a PostgreSQL integration or production
runtime proof.

## Independent review

The separate `approval_fake_review` verifier accepted the exact SQL/fake
contract, scope and source hashes, and independently reran the isolated suite
with `python3 -I -B`: 8/8 passed in 0.196 seconds. This statement records the
reviewer's reported rerun, distinct from the captured builder run above.

Final local static checks also passed with the repository's existing Ruff:

```text
venv/bin/ruff check --no-cache --select F821,F822,F823 tests/agent_blueprint_fakes.py tests/test_agent_blueprint_fake_approval_order.py
venv/bin/ruff check --no-cache tests/test_agent_blueprint_fake_approval_order.py
git diff --check
```

No new tooling dependency was installed.
