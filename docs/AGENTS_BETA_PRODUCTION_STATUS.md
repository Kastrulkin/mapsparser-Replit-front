# Agents Beta Production Status

This document is a dated evidence ledger for the controlled Agents beta. It is
not a promise that the rollout is complete. Mutable counters must be checked in
`/dashboard/bazich?tab=agents`; run-level evidence is available through the
support export attached to each scheduler event or failed run.

## Snapshot: 23 July 2026, 19:20 Europe/Moscow

### Deployed code

- Production runtime baseline: `b92ea505593b17d3ffd3567464b51c4f323e98ea`.
- The server branch `codex/agents-production-beta` is clean and byte-aligned
  with the published GitVerse/GitHub branch. A separate filesystem archive and
  local git snapshot preserve the pre-alignment production tree.
- Database revision: `20260722_003`.
- Verification: `319` agent tests, product UI guard and both Vite builds passed.
- `scripts/test_agents_docker.sh` is now deterministic: it installs the test
  dependencies in an ephemeral container and prevents live model credentials
  from leaking into the test process.
- Production smoke passed after a targeted `app` and `worker` restart: the
  database is healthy, migrations are current and the application returns
  HTTP 200.

### Durable queue and idempotent manual execution

Riderra blueprint `d659154e-4e93-460f-ae1e-ca3359b534a5` used active version
`a0bd42ef-26c7-46bd-8dcc-589a7878ef5e` for a production recovery canary.

Run `3725f285-82dd-4095-a946-d752de16d741` was queued while the worker was
stopped. Repeating the request with the same idempotency key returned the same
run with `reused=true`; a new key while the run was in progress returned
`AGENT_RUN_ALREADY_IN_PROGRESS`. The run was then moved to a stale heartbeat
state before any step started. After the worker restarted it recovered the run,
continued with attempt 2 and completed all four steps with one
`agent_final_result` and no approval.

The run created one two-credit reservation. It used no model tokens, so zero
credits were charged and both credits were released. Model-backed production
run `549394a3-bc42-4d69-8951-82d9e4457fdc` separately proves settlement: two
credits were reserved and charged exactly once.

This closes production proof for queue persistence, worker restart recovery,
stale-heartbeat retry, duplicate-request reuse, parallel-run rejection and a
single billing lifecycle per run.

### Scheduled canary, day 4 of 7

Both schedules belong to Riderra, are read-only, use `Europe/Tallinn` and have
run on four consecutive real dates. No synthetic backfill is counted.

| Date | 17:50 run | 18:20 run |
| --- | --- | --- |
| 20 July | `011cce34-78fb-448f-8ba1-d40653219026` | `827c4182-1cfc-4371-bf5a-a0b8a0e61c92` |
| 21 July | `86ece821-664c-4209-ae35-a4c6d866932a` | `bbc8bcda-0fba-4525-a3af-df9da4293266` |
| 22 July | `11334edb-c246-4ce6-99e0-20d83a201a89` | `da018624-2b8f-4fc7-94bb-c2256278fdda` |
| 23 July | `f6dcf941-f389-4081-962c-716e3ee36b3a` | `639e84d5-2096-4f97-9a32-520419acadb3` |

Every run completed with a result, used the active version and created no
approval or external action. There are no duplicate runs, failed events,
missed dates or starts outside the 15-minute canary limit. The formal gate
remains open through both scheduled runs on 26 July 2026.

### Proven non-Google scenarios

- Reviews to reply drafts: work run
  `6ddfc9ab-d21b-4a89-8ed2-cb1fd44ec616` completed with two reply drafts,
  provenance `reviews`, `publish_state=not_published` and
  `external_dispatch_performed=false`.
- Content draft: model-backed work run
  `549394a3-bc42-4d69-8951-82d9e4457fdc` saved a content result and charged the
  reserved two credits once.
- Safe internal manual result: recovery run
  `3725f285-82dd-4095-a946-d752de16d741` completed after a worker interruption
  and preserved its result.

External publication and sending were not performed in these proofs.

### Production state

- Queue after the recovery canary: zero queued, running, retry-wait,
  waiting-approval and stale runs.
- Archived unfinished runs: zero.
- Pending approvals on archived agents: zero.
- Active blueprints with an unconfirmed execution mode: zero.
- Scheduler failures in the preceding 24 hours: zero.
- Agent billing: zero active reservations; 72 credits reserved historically,
  14 charged and 58 released.
- Agent integrations: one active binding, zero ready Google bindings and one
  Google binding requiring reconnection.

Pilot counters at this snapshot:

| Business | Previews | Work runs | Completed | Success | Results | Feedback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HighSpeed and Go | 10 | 5 | 5 | 100% | 5 | 0 |
| Riderra (Tallinn) | 31 | 25 | 24 | 96% | 24 | 0 |
| Весёлая расчёска | 18 | 8 | 8 | 100% | 8 | 0 |

The admin Agents view exposes queue state, retries, failures, scheduler events
and canary progress, integration readiness, billing reservations, pilot gates
and downloadable support exports for scheduler events and failed runs.

### Open gates

1. Observe three more real scheduled dates: 24, 25 and 26 July. Synthetic
   backfill does not count.
2. Collect at least one genuine result evaluation from each pilot business.
   Developers must not submit feedback on behalf of users.
3. Riderra must reconnect Google OAuth. The current account is inactive with
   `invalid_grant` because the token was expired or revoked.
4. After reconnection, repeat Google Sheets to business result and Google
   Sheets to content-plan draft production E2E.
5. Run authenticated browser QA of the final owner flow. The current clean
   browser session reaches the login screen, so this must be completed in an
   authenticated owner session.
6. Run the final requirement-by-requirement audit before changing the rollout
   status from cohort beta.

External publication, sending, payments and destructive actions remain behind
the existing explicit approval boundary throughout the beta.
