# Client-info integration and card-growth unit slices

21 September 2026. Frozen application source remains `99849935`; parent audit
checkpoint `f9cbbae5`. No application, fixture, migration or assertion edits.
No production, existing database, provider, push or deployment action.

## Preserved failure and causal correction

The first unchanged `tests/test_client_info_gate.py` attempt collected eight
nodes: one static check passed, seven failed in fixture setup. Every failure
was at `src/main.py:240`, Flask-SQLAlchemy initialization without
`SQLALCHEMY_DATABASE_URI`. No endpoint assertion ran. The shared migration
fixture sets `DATABASE_URL` in its Alembic child only; importing `main` in the
pytest parent also requires that configuration. Patching the runtime DB
resolver does not configure Flask-SQLAlchemy. This is an isolated test
environment/fixture gap, not evidence of a production endpoint defect.

The support-only correction binds `DATABASE_URL` for `client-info-v1` after
the owned relay starts, its capability is revalidated and eight negative
capability cases pass. The parent must previously have no such environment
key. The URL names only the newly created synthetic `test` database and
literal owned loopback relay. Cleanup removes the exact injected value,
refuses to overwrite an unexpected changed value, and continues container
cleanup even if unbinding fails. Other profiles are unaffected. Pure helper
checks cover absent/empty/foreign configuration, foreign owner, invalid
capability, changed-value preservation and card-profile non-interference.

The original v1 raw failure is retained: pytest 9.90s, capture 10.968s,
wrapper 14.391s. Its container was removed and source/resources were preserved.

## Actual successful results

- Client-info v2: **8 collected / 8 passed**, no skips/xfails/setup/call errors,
  exit0 and empty stderr. Pytest 12.05s, capture 13.113s, wrapper 16.475s.
  Covers link retrieval, save/read, duplicate prevention, clearing links,
  implicit first business, nonexistent business404, static runtime contract,
  and committed changes visible to another connection.
- Ten guarded-IO negative probes and real stripped-environment child proof
  passed. Eight cause-specific capability negatives passed. One parent
  DATABASE_URL bind/unbind pair is recorded. Twenty-three DSN admissions
  include one non-connecting bind validation and **22 real relay connections**;
  all22 Docker execs exit0/graceful/empty stderr, no active/rejected/failed
  connections. Original32-total/8-concurrent limits were unchanged.
- Created tmpfs container
  `2d6209fe8629879d8e0553bdebb14ea25762833f985dd54783c6f0a31bb02467`
  was removed and its synthetic data discarded. Retained internal network
  and capability directory are empty. All29 existing Docker identities/
  running states match before/after; no existing volumes were deleted.
- Frozen source5720 tracked blobs/modes match before/after. Installed default
  guard07d3... was restored and temporary adapter/relay module copies removed.
  Independent read-only review accepted both the v1 cause and v2 result.
- Separate pure unit slice `tests/test_card_growth_copy_contract.py`:
  **200 collected / 200 passed**, no skips/errors/xfails, exit0, empty stderr.
  Pytest0.12s, capture0.568s, wrapper2.795s. It ran sequentially under the
  unchanged default guard, without DATABASE_URL, providers or TC mode. The
  reviewed tests require no DB/Docker/network operations. Guard and5720 source
  blobs match before/after, with postchecks also required on test failure.
  Independent read-only review matched the raw callbacks and all helper hashes
  and accepted this separate200-node scope.

Evidence: `native-client-info-hflypi-20260921/`, 15 raw/static captures plus
SHA-256 manifest. This includes both client attempts, the pure unit capture,
their logs and final static helper/Ruff6files/diff-check capture (exit0,
272.6ms). Raw current support hashes are captured; v1's earlier hashes are
retained as historical metadata, not claimed equal to the corrected adapter.

## Scope and next work

Together with the previous card-growth migration test, fresh backend evidence
now covers **209 distinct passed nodes / 5481 collected**. This is three
separate module slices, not one full-suite run:5272 nodes remain unexecuted.
The mapped94-node PostgreSQL-module group has85 remaining;5187 other nodes
remain. Do not count the v1 static pass twice or call this full readiness.

Next: additional useful pure-unit batches and the remaining PostgreSQL
fixture families, then aggregate checks. Default-parallel frontend failures,
security closure, real-API browser/captcha checks, performance, hosted CI and
the whole-goal completion gates remain open. Forced-crash cleanup is still
static-review-only. Historical whole-goal FAIL is unchanged.

Keep ARM64 tmux launchers,5GiB start/2GiB live floors, frozen source and
13foreign dirty paths. Do not replay completed cache/build/restore/collection
or these slices. After the unit slice free space was6,348,066,816bytes
(~5.91GiB); no additional cache cleanup is claimed in this checkpoint.
