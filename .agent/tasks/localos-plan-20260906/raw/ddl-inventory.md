# Active runtime DDL inventory — 2026-09-06

Callers were mapped from registered routes, job dispatch and singleton construction. Definition-only matches are not treated as active. Historical migration/bootstrap scripts are separate from runtime paths. No global DDL privilege revocation is authorized by this inventory.

| Runtime module | Active entry/caller | Parity / migration | Status |
| --- | --- | --- | --- |
| services/content_plan_service | content-plan context, generation and feedback | 20260430, 20260505, 20260830 + 20260906_003 | Runtime now read-only checks |
| core/ai_learning | record_ai_learning_event | 20260906_003 | Runtime now read-only checks |
| services/operator_news_generation | operator API, Operator core, social generation | usernews parity 20260906_003 | Runtime now read-only checks |
| core/card_automation | worker card jobs, legacy routes | 20260420 schema | Runtime now read-only checks |
| core/parsing_runtime_config | worker, bot, parsing/dashboard routes | 20260906_004 | Runtime now read-only checks |
| core/db_helpers | user-example read/write | 20260803 | Runtime now read-only checks |
| services/operator_services_optimization | services menu optimization | 20260505_001 | Runtime now read-only checks |
| services/agent_domain_request_executors | communication/review apply journals | 20260609 | Runtime now read-only checks |
| core/action_orchestrator + action_ledger | execute/callback; Operator, capabilities API, agent runner, worker, Telegram singleton | 20260906_005 | Runtime now read-only checks |
| core/growth_schema | admin growth CRUD, stage progress, network health | 20260906_006 + idempotent default type seed | Runtime now read-only checks |
| core/industry_pattern_recalibration | admin, Telegram and public request feedback | 20260506_001/002 + 20260906_009 | Runtime now read-only checks |
| ai_agents_api | registered persona/config CRUD | legacy parity + 20260906_009 | Runtime now read-only checks |
| api/wordstat_api | optional registered keyword routes | 20260906_009 | Runtime now read-only checks |
| services/agent_capability_handlers | registered capability execution | 20260609 request tables; read-only guards verified on full staging chain | Runtime now read-only checks |
| api/prospecting/access_schema + audit_routes | search, delivery, outreach, sales-room routes | 20260421/20260617/18/29/20260830 + 20260906_011/012 | Runtime now read-only checks; real full-chain staging DML proof |
| legacy_routes/report_pipeline | public offer/report request pipeline | 20260906_010 | Runtime now read-only checks |
| telegram_bot | callback recovery, support export history | 20260906_010 + existing UserNews migrations | Runtime now read-only checks |
| database_manager.init_database_schema | explicit migration/debug script call sites only; not normal app startup | historical bootstrap | Excluded from runtime claim; retain script-only boundary |
| finance/average-ticket/telegram-control scope | schema existence probes | no DDL in inspected probes | Read-only, retain |

The app/worker may switch globally to a DML-only role only after every remaining active startup/request/job branch has migration parity and the same operation succeeds with CREATE/ALTER/DROP denied. Passing the content and action slices alone does not meet that gate.

## Remaining source hits after these transfers

A wider final search found additional DDL literals outside the initial caller inventory. They are **not covered by the transfers above**. Before any global DML-only cutover, map registered routes/jobs and prove schema parity for:

- `legacy_routes/content_services.py`, `public_requests.py`, `auth_admin.py`, `client_reports.py`;
- `telegram_reviews_bot.py`, `core/agent_api_security.py`, `worker.py`, `ai_agent_tools.py`;
- `api/admin_industry_patterns_api.py`, `api/growth_workflow_api.py`, `messengers_api.py`.

Definition-only/historical matches remain separately: `src/migrations/*`, `init_growth_db.py`, `init_database_schema.py`, `update_wordstat_data.py`. The search alone does not establish that each definition executes at runtime. App-wide DDL retirement is not complete; do not revoke production DDL rights on this evidence.

Actual full-chain staging proof: `raw/staging-dml-role.json` checks 13 helpers at Alembic head `20260906_012`, denies CREATE/ALTER/DROP and preserves the caller savepoint. `test_prospecting_runtime_schema_pg.py` alone uses a narrow schema-equivalent fixture and is not full migration evidence.
