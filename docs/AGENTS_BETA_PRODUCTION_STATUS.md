# Agents Beta Production Status

This document is a dated evidence ledger for the controlled Agents beta. It is
not a promise that the rollout is complete. Mutable counters must be checked in
`/dashboard/bazich?tab=agents`; run-level evidence is available through the
support export attached to each scheduler event or failed run.

## Snapshot: 20 July 2026, 18:23 Europe/Moscow

### Deployed code

- Production runtime baseline: `4b116fa6920dc1fb48dbb7d3acaa54c06d425937`.
- At runtime deployment the server branch `codex/agents-production-beta` was
  clean and aligned with the published GitVerse/GitHub branch. Later docs-only
  commits do not change this container runtime baseline.
- Database revision: `20260720_002`.
- Verification: `295` agent tests, product UI guard and both Vite builds passed.
- The live Agents chunk contains run recovery after reload and per-run beta
  feedback. Browser QA opened the exact newly completed run after reload.

### Manual reusable execution

Riderra blueprint `d659154e-4e93-460f-ae1e-ca3359b534a5` used active version
`a0bd42ef-26c7-46bd-8dcc-589a7878ef5e` for separate production runs with
different inputs:

| Run | Input | Result |
| --- | --- | --- |
| `d3955fea-2f7d-48fa-8f3b-9ea32a3900c6` | summary for 27 July and duplicate-start check | completed, one `agent_final_result` |
| `e3316b3b-1638-4006-8a18-371a489fdee2` | reload-recovery check on 20 July | completed after browser reload, one `agent_final_result` |

Each run has one idempotency key and one reservation. These internal summaries
used zero model tokens, so the full two-credit reservation was released. A
separate model-backed production run, `549394a3-bc42-4d69-8951-82d9e4457fdc`,
proves actual settlement: two credits reserved and two charged exactly once.

### Scheduled canary, day 1 of 7

Both schedules belong to Riderra, are read-only and use `Europe/Tallinn`.

| Schedule | Blueprint / active version | 20 July run | Evidence |
| --- | --- | --- | --- |
| 17:50 | `b070474d-fa8c-45c8-99c3-3a20d2c10c10` / `c9409f7f-d4ce-4145-b770-53192cbe6b68` | `011cce34-78fb-448f-8ba1-d40653219026` | completed, one result, no approval or external action |
| 18:20 | `3051ce74-1943-4112-95f7-684eccc959e4` / `d7cb0b60-34c1-4cc9-92bf-47f065aa7fb2` | `827c4182-1cfc-4371-bf5a-a0b8a0e61c92` | completed, one result, no approval or external action |

The second slot started at 18:22 local time, within the 15-minute canary limit.
Both idempotency keys have exactly one run. The UI shows the next executions on
21 July at 17:50 and 18:20. The gate remains open until both schedules complete
seven consecutive real dates without a miss, duplicate, old-version run or
external action.

### Production state

- Queue after both canaries: zero queued, running, retry-wait, waiting-approval
  and stale runs.
- Archived unfinished runs: zero.
- Pending approvals on archived agents: zero.
- Active blueprints with an unconfirmed execution mode: zero.
- Scheduler failures in the preceding 24 hours: zero.

Pilot counters at this snapshot:

| Business | Previews | Work runs | Completed | Success | Results | Feedback |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HighSpeed and Go | 10 | 5 | 5 | 100% | 5 | 0 |
| Riderra (Tallinn) | 31 | 18 | 17 | 94.4% | 17 | 0 |
| Весёлая расчёска | 18 | 8 | 8 | 100% | 8 | 0 |

### Open gates

1. Observe six more real scheduled dates. Synthetic backfill does not count.
2. Collect at least one genuine result evaluation from each pilot business.
   Developers must not submit feedback on behalf of users.
3. Riderra must reconnect Google OAuth. The current account is inactive with
   `invalid_grant` because the token was expired or revoked.
4. After reconnection, repeat Google Sheets to business result and Google
   Sheets to content-plan draft production E2E.
5. Run the final requirement-by-requirement audit before changing the rollout
   status from cohort beta.

External publication, sending, payments and destructive actions remain behind
the existing explicit approval boundary throughout the beta.
