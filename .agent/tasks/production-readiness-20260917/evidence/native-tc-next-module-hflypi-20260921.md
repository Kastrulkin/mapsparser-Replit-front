# Next bounded PostgreSQL module — not executed

Read-only follow-up to the accepted one-node Testcontainers proof.

Candidate command target: `tests/test_client_info_gate.py`.
The existing frozen collection has 8 nodes: 7 PostgreSQL endpoint cases plus
one static source check. All share one module-scoped container and one Flask
migration child, with the same `test` user/password/database. Tests create
per-test `test_<uuid>` schemas, not child databases, and use Flask test_client.

Review only the required literal `client-info-v1` mode/target/count change;
retain exact image/internal network/tmpfs/relay ownership, environment
inheritance, guarded DSN, no skips and exact cleanup. Count connection demand
against the current bounded relay budget before execution. Source and
assertions must remain unchanged. This recommendation is not runtime proof.

Do not yet include child-database rollback/concurrency modules:
`test_creator_offer_distribution_migration_rollback.py`,
`test_creator_portal_migration_rollback.py`,
`test_finance_import_transaction_pg.py`,
`test_service_compression_apply_concurrency_pg.py`,
`test_work_review_migration_rollback.py`.
`test_web_tracking_postgres.py` has additional upgrade/downgrade children.
Sales-room/service concurrency and the 57-node capability API module also
need their own reviewed threading/resolver/namespace profile before admission.
