# Dashboard query evidence bridge — 22 September 2026

Scope: historical query proof at `20431224`, sustained localhost reads at
`272794a4`, current tracked source `d0ef4ce84c89e33a967429e570fb6e08821911a7`.
Read-only source review, not a new runtime measurement. Foreign worktree changes
are excluded. Root and a separate performance reviewer inspected the exact paths.

## Accepted narrow bridge

The timed handlers are `auth_user_api.get_user_info` (`/api/auth/me`) and
`legacy_routes.public_requests.get_business_data` (`/api/business/<id>/data`).
The latter uses `verify_session`, `DatabaseManager.get_business_by_id`,
`verify_business_access`, services/finance/reports reads and a BusinessProfiles
select. These handler/helper paths are unchanged between the stated refs.

Root ran:

```sh
git diff --exit-code 20431224 d0ef4ce8 -- src/main.py src/api/auth_user_api.py src/database_manager.py src/core/auth_helpers.py alembic_migrations migrations
git diff --stat 20431224 d0ef4ce8 -- src/auth_system.py
git diff 20431224 d0ef4ce8 -- src/legacy_routes/public_requests.py
git diff 20431224 d0ef4ce8 -- scripts/readiness_query_plans.py
git diff --stat 272794a4 d0ef4ce8 -- scripts/readiness_journey_load.py
```

The first comparison exits0 with no diff; auth_system and load harness are also
unchanged. The only public_requests change is the separate `confirm_reset`
handler (47 additions/16 deletions), outside this request path. Query harness
changes only its docstring and route_note; the counted dispatch and three
representative SQL expressions are unchanged.

The independent middleware review finds unchanged before_request hooks:
`remember_web_tracking_request_start` only acts on tracking/events;
`require_legacy_maps_content_access` only acts on news/review paths. Both return
without authentication DB work for these two reads. No relevant blueprint hook
or default/route rate limit was found. Unchanged handlers alone were not used
to infer middleware equivalence.

Therefore the historical 4-read auth count and 9-read/0-DDL business-data count,
plus ACCESS_QUERY/SERVICES_QUERY/CARDS_QUERY shapes and migrated tiny-fixture
schema, remain relevant to this exact current-source path. This is not every
business query or a representative large-tenant plan: the fixture has one
business/one service/zero cards, and access SQL omits dynamic parser/moderation
filters. No new index or cache is justified by it.

## What is not bridged

Historical latency, CPU/RSS and plan execution-time numbers remain observations
of their original runs. Equivalent handlers/middleware do not establish equal
current runtime import/memory layout, host pressure or process-resource use.
The240-read historical load's scenario remains structurally relevant, but a
fresh bounded local load/resource observation is still required for current
numeric AC7 evidence. Frontend has changed and needs its own bounded refresh.
Production capacity/SLO or live-provider load are not added as completion gates.

Original captures remain in task raw `query-proof-20431224{,.child,-command}.json`
and `http-sustained-272794a4{,-command}.json`. Old temporary launcher paths are
absent and must not be replayed. Reusable maintained harnesses are
`scripts/readiness_query_plans.py` and `scripts/readiness_journey_load.py`.
