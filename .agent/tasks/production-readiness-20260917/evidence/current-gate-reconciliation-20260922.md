# Current gate reconciliation — 22 September 2026

Checkpoint: committed HEAD `202b9c95afc58a2e2d5ebb3fb89523700bcb6892`.
This is evidence reconciliation, not a new aggregate pass or release approval.

## Python CI gate

The actual project command `scripts/ci_gate_python_f821.sh` passes on the
current working tree: exit 0, 164.514 ms, no timeout or truncation. This is the
F821-only CI gate, not full Python lint. Its explicit exclusions remain:
prospecting dynamic fragments, admin_prospecting, legacy_routes, social_posts
fragments, migrations and one-off scripts. Existing dirty source was not edited.

Exact command and retained captures:

```text
env RUFF_NO_CACHE=true PYTHON_BIN=/private/tmp/localos-readiness-20260921.hfLYPi/native/venv/bin/python bash scripts/ci_gate_python_f821.sh
```

- `current-gate-reconciliation-20260922/current-f821-v2.json`: successful capture.
- `current-gate-reconciliation-20260922/current-f821-v1.json`: first command
  used invalid `RUFF_NO_CACHE=1`; exit 2, 65.693 ms, before analysis. This is a
  command setup error, not a product finding.
- Gate SHA-256: `5fe6ec6fc01e7cfde5ff77b1b076528cfc61b513f54f1779d04c334198a2e058`.

## Existing compiled-runner proof is current-source relevant

The two nodes in `tests/test_compiled_runner_load.py` already passed in
`capability-linux-20260922/exact13-v4.json`, using clean commit
`b12cfcb25925162811a37408dee2820138ca22fa`. All six setup/call/teardown records
for these two nodes are passed, with no xfail. This was a network-none Linux
container test with its permitted internal loopback, not a live provider test.

Both runtime and test bytes remain identical at current HEAD and in the working
tree. The Git diff between the two commits is empty for these paths:

- `docker/compiled-script-runner/server.py`:
  `efcf952408a250b07846804e95a241bfcd3997a8c03f82f835baaa112469a408`.
- `tests/test_compiled_runner_load.py`:
  `346740a21d91081e800cce99bdc4bfb9ee583ff547264afbda4ffa02a6028593`.

Do not reinterpret the older admission inventory's three loopback fixture uses
as three new/unverified tests. Do not rerun this covered pair just to grow counts.
This source bridge does not turn the entire failed offline aggregate green.

## Seven genuinely missing PostgreSQL proofs, subsequently executed

The exact d0ef aggregate records seven setup skips in these two modules, not
successful calls. Their tests, two migrations and three relevant core modules
are unchanged between the clean snapshots and current committed source:

- `tests/test_action_orchestrator_schema_pg.py`: three nodes;
  SHA-256 `e8d8051bd8c31daae3eb1cc2d0e23e4bd016a9401a7d6e704815cbbeedb3efd7`.
- `tests/test_agent_api_security_runtime_pg.py`: four nodes;
  SHA-256 `a2ec0288c55619027123f3cbab60b6d586ae560cff2a6e643e114833a9b382da`.

Next execution must use a fresh owned local PostgreSQL cluster and a generated
test database, never inherited `DATABASE_URL`. Fixtures apply the two actual
migrations twice; exercise DML-only roles, denied DDL, schema errors, ledger
writes and rollback. Their temporary NOLOGIN roles are cluster-global, so run
serially and independently verify both schema and role absence before stopping
the exact owned postmaster. No Docker, provider or production action is needed.
The reviewed follow-up now passes7/7 with21stages and independently accepted
cleanup. Actual evidence is recorded separately in
`schema-security-pg7-results-20260922.md`; this historical skip record is not
rewritten or added arithmetically to the failed aggregate.

## Security ledger correction

The pinned image has 219 mapped candidates: 13 classified by exact whole-file
source equality; **206 remain unresolved**. The earlier 219-untriaged checkpoint
is historical. Three private-key delimiter observations explain only those
specific detector signals and do not clear their members or reduce this open
ledger. Source: `image-candidate-map-results-20260922.md` and
`image-pem-observations-results-20260922.md`. No credential is tested externally.

A proposed structural-image helper was rejected before execution: its process
cleanup ordering, error-path cleanup and bounds needed correction. The helper
was then made fail-closed and was not adopted. Only synthetic predicate checks
ran; no Docker command or new image read occurred. Its temporary status note is
`/private/tmp/localos-image-structural-v1.QqytCs/STATUS.md`. This preparation
failure is not a new image finding or clearance; the206-open count is unchanged.

## Independent review

A separate read-only reviewer verified both F821 capture hashes, independently
parsed the two runner nodes' six passed stages, checked their b12/current byte
equality, and found exactly seven setup skips/no calls in the historical full
callback. The reviewer accepted this bounded reconciliation and the corrected
security count. This is not acceptance of any proposed runtime controller or
the whole-project definition of done.

## Boundaries

The restricted secondary OAuth candidate and native finance picker are not run
or routed around. Foreign tracked/untracked changes are preserved; the pending
author/diagnostic fixture-adoption choice is unchanged. No production mutation,
push, deploy, extra cleanup or new whole-project readiness assertion.
